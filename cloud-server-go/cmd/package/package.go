package main

import (
	"archive/tar"
	"compress/gzip"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

var (
	cloudAgentDir  = "c:\\yj\\CloudRealm\\cloud-agent"
	buildDir       = "c:\\yj\\CloudRealm\\cloud-server-go\\cmd\\package\\build"
	workspaceDir   string
	agentVersion   = "1.0.0"
	agentName      = "cloud-agent"
)

func main() {
	var err error
	workspaceDir, err = os.Getwd()
	if err != nil {
		fmt.Printf("Failed to get working directory: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("=== Cloud Agent Package Tool ===\n")
	fmt.Printf("Workspace: %s\n", workspaceDir)
	fmt.Printf("Go Version: %s\n", runtime.Version())
	fmt.Printf("OS/Arch: %s/%s\n\n", runtime.GOOS, runtime.GOARCH)

	if err := os.MkdirAll(buildDir, 0755); err != nil {
		fmt.Printf("Failed to create build directory: %v\n", err)
		os.Exit(1)
	}

	if err := buildGoBinary(); err != nil {
		fmt.Printf("Build failed: %v\n", err)
		os.Exit(1)
	}

	if err := copyPythonSource(); err != nil {
		fmt.Printf("Copy Python source failed: %v\n", err)
		os.Exit(1)
	}

	if err := copyConfigFiles(); err != nil {
		fmt.Printf("Copy config failed: %v\n", err)
		os.Exit(1)
	}

	if err := copyInstallScripts(); err != nil {
		fmt.Printf("Copy install scripts failed: %v\n", err)
		os.Exit(1)
	}

	if err := createTarGz(); err != nil {
		fmt.Printf("Create tar.gz failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("\n=== Package Complete ===")
	pkgName := fmt.Sprintf("%s-%s.tar.gz", agentName, agentVersion)
	fmt.Printf("Package: %s\n", filepath.Join(buildDir, pkgName))
	fmt.Println("\nTo install on Linux server:")
	fmt.Println("  1. Copy the package to your Linux server")
	fmt.Println("  2. Run: tar -xzf cloud-agent-1.0.0.tar.gz")
	fmt.Println("  3. Run: cd cloud-agent-1.0.0 && ./install.sh")
}

func buildGoBinary() error {
	fmt.Println("[1/5] Building cloud-agent Go binary for Linux...")

	binaryName := "cloud-agent"
	outputPath := filepath.Join(buildDir, binaryName)

	cmd := exec.Command("go", "build", "-o", outputPath, "-ldflags", "-s -w")
	cmd.Dir = cloudAgentDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	cmd.Env = os.Environ()
	cmd.Env = append(cmd.Env, "GOOS=linux", "GOARCH=amd64")

	err := cmd.Run()
	if err != nil {
		return fmt.Errorf("go build failed: %v", err)
	}

	fileInfo, err := os.Stat(outputPath)
	if err == nil {
		fmt.Printf("Built: %s (%.2f MB)\n", outputPath, float64(fileInfo.Size())/1024/1024)
	}

	return nil
}

func copyPythonSource() error {
	fmt.Println("[2/5] Copying Python source...")

	pythonDestDir := filepath.Join(buildDir, "python")
	if err := os.MkdirAll(pythonDestDir, 0755); err != nil {
		return err
	}

	pythonSrcDir := filepath.Join(cloudAgentDir, "src", "main", "python")

	files := []string{"setup.py", "setup.cfg"}

	for _, file := range files {
		src := filepath.Join(pythonSrcDir, file)
		dst := filepath.Join(pythonDestDir, file)

		data, err := os.ReadFile(src)
		if err != nil {
			if os.IsNotExist(err) {
				continue
			}
			return err
		}

		if err := os.WriteFile(dst, data, 0644); err != nil {
			return err
		}
	}

	cloudAgentSrc := filepath.Join(pythonSrcDir, "cloud_agent")
	cloudAgentDst := filepath.Join(pythonDestDir, "cloud_agent")

	if err := os.MkdirAll(cloudAgentDst, 0755); err != nil {
		return err
	}

	return filepath.Walk(cloudAgentSrc, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			relPath, _ := filepath.Rel(cloudAgentSrc, path)
			newPath := filepath.Join(cloudAgentDst, relPath)
			return os.MkdirAll(newPath, 0755)
		}

		relPath, _ := filepath.Rel(cloudAgentSrc, path)
		newPath := filepath.Join(cloudAgentDst, relPath)

		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}

		return os.WriteFile(newPath, data, 0644)
	})
}

func copyConfigFiles() error {
	fmt.Println("[3/5] Copying config files...")

	confDestDir := filepath.Join(buildDir, "conf")
	if err := os.MkdirAll(confDestDir, 0755); err != nil {
		return err
	}

	confDir := filepath.Join(cloudAgentDir, "conf", "unix")
	files := []string{
		"cloud-agent",
		"cloud-agent.ini",
		"cloud-env.sh",
		"install-helper.sh",
		"logging.conf.sample",
		"cloud-sudo.sh",
	}

	for _, file := range files {
		src := filepath.Join(confDir, file)
		dst := filepath.Join(confDestDir, file)

		data, err := os.ReadFile(src)
		if err != nil {
			if os.IsNotExist(err) {
				continue
			}
			return err
		}

		perm := int64(0644)
		if strings.HasPrefix(file, "cloud-") && !strings.Contains(file, ".ini") && !strings.Contains(file, ".conf") {
			perm = 0755
		}

		if err := os.WriteFile(dst, data, os.FileMode(perm)); err != nil {
			return err
		}
	}

	return nil
}

func copyInstallScripts() error {
	fmt.Println("[4/5] Copying install scripts...")

	scriptsDestDir := filepath.Join(buildDir, "scripts")
	if err := os.MkdirAll(scriptsDestDir, 0755); err != nil {
		return err
	}

	rpmScriptsDir := filepath.Join(cloudAgentDir, "src", "main", "package", "rpm")
	scripts := []string{
		"preinstall.sh",
		"postinstall.sh",
		"preremove.sh",
		"postremove.sh",
	}

	for _, script := range scripts {
		src := filepath.Join(rpmScriptsDir, script)
		dst := filepath.Join(scriptsDestDir, script)

		data, err := os.ReadFile(src)
		if err != nil {
			if os.IsNotExist(err) {
				continue
			}
			return err
		}

		if err := os.WriteFile(dst, data, 0755); err != nil {
			return err
		}
	}

	installScript := `#!/bin/bash
# Cloud Agent Installation Script
# Version: ` + agentVersion + `

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/usr/local/cloud-agent"
LOG_DIR="/usr/local/cloud-agent/log"

echo "=== Cloud Agent Installer ==="
echo "Version: ` + agentVersion + `"
echo "Install Directory: $INSTALL_DIR"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root"
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR/bin"
mkdir -p "$INSTALL_DIR/python"
mkdir -p "$INSTALL_DIR/conf"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$LOG_DIR"

# Install binary
echo "Installing binary..."
cp -f "$SCRIPT_DIR/cloud-agent" "$INSTALL_DIR/bin/"
chmod 755 "$INSTALL_DIR/bin/cloud-agent"

# Install Python packages
echo "Installing Python packages..."
cp -rf "$SCRIPT_DIR/python/"* "$INSTALL_DIR/python/"
chmod -R 755 "$INSTALL_DIR/python"

# Install config files
echo "Installing config files..."
cp -f "$SCRIPT_DIR/conf/cloud-agent.ini" "$ETC_DIR/conf/"
cp -f "$SCRIPT_DIR/conf/cloud-agent" "$ETC_DIR/conf/"
cp -f "$SCRIPT_DIR/conf/cloud-env.sh" "$ETC_DIR/conf/"
cp -f "$SCRIPT_DIR/conf/logging.conf.sample" "$ETC_DIR/conf/"

chmod 644 "$ETC_DIR/conf/"*

# Install scripts
echo "Installing scripts..."
cp -f "$SCRIPT_DIR/scripts/"* "$ETC_DIR/scripts/"
chmod 755 "$ETC_DIR/scripts/"*

# Install Python dependencies
echo "Installing Python dependencies..."
if command -v python3 &> /dev/null; then
    pip3 install -r "$INSTALL_DIR/python/requirements.txt" 2>/dev/null || true
fi

# Start service (optional)
echo ""
echo "=== Installation Complete ==="
echo ""
echo "To start cloud-agent:"
echo "  $INSTALL_DIR/bin/cloud-agent -server http://your-server:8080 -id your-hostname"
echo ""
echo "Or configure as systemd service:"
echo "  cp /usr/local/cloud-agent/conf/cloud-agent /etc/init.d/"
echo "  chkconfig --add cloud-agent"
echo ""

exit 0
`

	if err := os.WriteFile(filepath.Join(buildDir, "install.sh"), []byte(installScript), 0755); err != nil {
		return err
	}

	uninstallScript := `#!/bin/bash
# Cloud Agent Uninstallation Script

set -e

INSTALL_DIR="/usr/local/cloud-agent"

echo "=== Cloud Agent Uninstaller ==="

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root"
    exit 1
fi

echo "Stopping service..."
if [ -f /etc/init.d/cloud-agent ]; then
    service cloud-agent stop 2>/dev/null || true
fi

echo "Removing files..."
rm -rf "$INSTALL_DIR"

echo "=== Uninstallation Complete ==="
exit 0
`

	if err := os.WriteFile(filepath.Join(buildDir, "uninstall.sh"), []byte(uninstallScript), 0755); err != nil {
		return err
	}

	return nil
}

func createTarGz() error {
	fmt.Println("[5/5] Creating tar.gz package...")

	tarPath := filepath.Join(buildDir, fmt.Sprintf("%s-%s.tar.gz", agentName, agentVersion))

	f, err := os.Create(tarPath)
	if err != nil {
		return err
	}
	defer f.Close()

	gzipWriter := gzip.NewWriter(f)
	defer gzipWriter.Close()

	tarWriter := tar.NewWriter(gzipWriter)
	defer tarWriter.Close()

	prefix := fmt.Sprintf("%s-%s", agentName, agentVersion)

	return filepath.Walk(buildDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		name := strings.TrimPrefix(path, buildDir+string(filepath.Separator))
		if name == "" || strings.HasSuffix(name, ".tar.gz") {
			return nil
		}

		header, err := tar.FileInfoHeader(info, filepath.Join(prefix, name))
		if err != nil {
			return err
		}

		if err := tarWriter.WriteHeader(header); err != nil {
			return err
		}

		if !info.IsDir() {
			data, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			if _, err := tarWriter.Write(data); err != nil {
				return err
			}
		}

		return nil
	})
}
