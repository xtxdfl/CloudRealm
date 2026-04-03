import os
import sys
import shutil

service_dir = r"c:\yj\CloudRealm\cloud-agent\service"

def fix_all_imports():
    fixed_count = 0
    
    for root, dirs, files in os.walk(service_dir):
        for f in files:
            if not f.endswith('.py'):
                continue
            
            filepath = os.path.join(root, f)
            rel_path = os.path.relpath(filepath, service_dir)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
            except Exception as e:
                print(f"Cannot read {rel_path}: {e}")
                continue
            
            new_content = content
            
            import_patterns = [
                ("from cloud_agent.", "from "),
                ("import cloud_agent.", "import "),
            ]
            
            for old, new in import_patterns:
                if old in new_content:
                    new_content = new_content.replace(old, new)
                    fixed_count += 1
            
            if content != new_content:
                try:
                    with open(filepath, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    print(f"Fixed: {rel_path}")
                except Exception as e:
                    print(f"Cannot write {rel_path}: {e}")
    
    print(f"\nTotal replacements: {fixed_count}")

if __name__ == "__main__":
    fix_all_imports()