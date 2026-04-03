#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import subprocess
import hashlib
import json
import configparser
from typing import List, Dict, Any, Optional
from pathlib import Path

class YumPackageParser:
    def __init__(self, repo_file: str = "/etc/yum.repos.d/cloud.repo"):
        self.repo_file = repo_file
        self.packages: List[Dict[str, Any]] = []
        self.repo_info: Dict[str, Any] = {}

    def load_repo_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.repo_file):
            raise FileNotFoundError(f"Repo file not found: {self.repo_file}")

        config = configparser.ConfigParser()
        config.read(self.repo_file)

        repo_sections = {}
        for section in config.sections():
            repo_sections[section] = dict(config.items(section))

        self.repo_info = {
            "repo_file": self.repo_file,
            "repos": repo_sections,
            "repo_names": list(repo_sections.keys())
        }
        return self.repo_info

    def get_available_packages(self, repo_name: Optional[str] = None) -> List[Dict[str, Any]]:
        cmd = ["yum", "list", "available", "--disablerepo=*"]
        
        if repo_name:
            cmd.extend(["--enablerepo=" + repo_name])
        else:
            for r in self.repo_info.get("repo_names", []):
                cmd.append("--enablerepo=" + r)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            output = result.stdout
        except subprocess.TimeoutExpired:
            return []
        except FileNotFoundError:
            return self._parse_from_xml()

        packages = []
        
        for line in output.split("\n"):
            line = line.strip()
            if not line or line.startswith("Available Packages") or line.startswith("Loaded"):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                name_arch = parts[0]
                version = parts[1]
                
                if "." in name_arch and "." in version:
                    name, arch = name_arch.rsplit(".", 1)
                    ver, rel = version.rsplit("-", 1) if "-" in version else (version, "")
                    
                    pkg = {
                        "name": name,
                        "arch": arch,
                        "version": ver,
                        "release": rel,
                        "repo": repo_name or "cloud"
                    }
                    packages.append(pkg)
        
        self.packages = packages
        return packages

    def _parse_from_xml(self) -> List[Dict[str, Any]]:
        import glob
        
        packages = []
        
        xml_patterns = [
            "/var/cache/yum/*/repodata/*-primary.xml.gz",
            "/var/cache/yum/*/repodata/primary.xml"
        ]
        
        for xml_pattern in xml_patterns:
            xml_files_found = glob.glob(xml_pattern)
            for xml_file in xml_files_found:
                try:
                    if xml_file.endswith(".gz"):
                        import gzip
                        with gzip.open(xml_file, 'rt') as f:
                            content = f.read()
                    else:
                        with open(xml_file, 'r') as f:
                            content = f.read()
                    
                    packages.extend(self._parse_primary_xml(content))
                except Exception:
                    continue
        
        return packages

    def _parse_primary_xml(self, content: str) -> List[Dict[str, Any]]:
        import xml.etree.ElementTree as ET
        
        packages = []
        
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return packages
        
        ns = {"p": "http://linux.du.se/schema/1"}
        
        for pkg in root.findall(".//p:package", ns) or root.findall(".//package"):
            name_elem = pkg.find("p:name", ns) or pkg.find("name")
            version_elem = pkg.find("p:version", ns) or pkg.find("version")
            arch_elem = pkg.find("p:arch", ns) or pkg.find("arch")
            size_elem = pkg.find("p:size", ns) or pkg.find("size")
            checksum_elem = pkg.find("p:checksum", ns) or pkg.find("checksum")
            
            pkg_info = {
                "name": name_elem.text if name_elem is not None else "",
                "version": version_elem.get("ver", "") if version_elem is not None else "",
                "release": version_elem.get("rel", "") if version_elem is not None else "",
                "arch": arch_elem.text if arch_elem is not None else "x86_64",
                "size": int(size_elem.get("size", "0")) if size_elem is not None else 0,
            }
            
            if checksum_elem is not None:
                pkg_info["checksum"] = checksum_elem.text
                pkg_info["checksum_type"] = checksum_elem.get("type", "sha256")
            
            provides = []
            for prov in pkg.findall("p:provides/p:entry", ns) or pkg.findall("provides/entry"):
                provides.append(prov.get("name", ""))
            if provides:
                pkg_info["provides"] = provides
            
            requires = []
            for req in pkg.findall("p:requires/p:entry", ns) or pkg.findall("requires/entry"):
                requires.append(req.get("name", ""))
            if requires:
                pkg_info["requires"] = requires
            
            packages.append(pkg_info)
        
        return packages

    def get_package_details(self, package_name: str) -> Dict[str, Any]:
        cmd = ["rpm", "-qpi", package_name]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {}

        details = {}
        for line in output.split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            
            if key == "Name":
                details["name"] = value
            elif key == "Version":
                details["version"] = value
            elif key == "Release":
                details["release"] = value
            elif key == "Architecture":
                details["arch"] = value
            elif key == "Size":
                details["size"] = value
            elif key == "Summary":
                details["summary"] = value
            elif key == "Description":
                details["description"] = value
        
        return details

    def calculate_md5(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        
        return md5_hash.hexdigest()

    def calculate_sha256(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()

    def export_packages_json(self, output_file: str):
        with open(output_file, 'w') as f:
            json.dump({
                "repo_info": self.repo_info,
                "packages": self.packages
            }, f, indent=2)

    def parse_cloud_repo(self, repo_name: str = "cloud") -> Dict[str, Any]:
        self.load_repo_config()
        
        packages = self.get_available_packages(repo_name)
        
        service_packages = {}
        stack_services = {
            "HDFS": ["hadoop", "hadoop-hdfs"],
            "YARN": ["hadoop", "hadoop-yarn"],
            "ZooKeeper": ["zookeeper"],
            "Spark": ["spark"],
            "Hive": ["hive", "hadoop-hcatalog"],
            "Kafka": ["kafka"],
            "Flink": ["flink"],
            "Doris": ["doris"],
            "Trino": ["trino"],
            "ElasticSearch": ["elasticsearch"],
            "Prometheus": ["prometheus"],
            "Grafana": ["grafana"],
            "HBase": ["hbase"],
        }
        
        for pkg in packages:
            pkg_name = pkg.get("name", "")
            for service, patterns in stack_services.items():
                for pattern in patterns:
                    if self._match_pattern(pkg_name, pattern):
                        if service not in service_packages:
                            service_packages[service] = []
                        service_packages[service].append(pkg)
                        break
        
        return {
            "repo_name": repo_name,
            "repo_info": self.repo_info,
            "packages": packages,
            "services": service_packages,
            "total_packages": len(packages)
        }

    def _match_pattern(self, name: str, pattern: str) -> bool:
        if "*" in pattern:
            import fnmatch
            return fnmatch.fnmatch(name, pattern)
        return name == pattern or name.startswith(pattern.rstrip("*"))

def main():
    import sys
    
    repo_name = "cloud"
    if len(sys.argv) > 1:
        repo_name = sys.argv[1]
    
    parser = YumPackageParser()
    
    try:
        result = parser.parse_cloud_repo(repo_name)
        print(json.dumps(result, indent=2))
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()