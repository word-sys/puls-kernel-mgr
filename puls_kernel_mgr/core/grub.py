import os
import subprocess
from fospx_kernel_mgr.core.grub_backup import GrubBackupManager

class GrubManager:
    def __init__(self):
        self.grub_default_path = "/etc/default/grub"
        self.custom_script_path = "/etc/grub.d/15_fospx_kernels"
        self.backup = GrubBackupManager()
        
    def read_default_config(self):
        config = {}
        if not os.path.exists(self.grub_default_path):
            return config
            
        with open(self.grub_default_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    config[key] = val.strip('"\'')
        return config

    def validate_dry_run(self):
        try:
            subprocess.run(["grub-mkconfig", "-o", "/tmp/grub.cfg.test"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

    def write_advanced_config(self, new_config):
        self.backup.create_snapshot()
        
        if not os.path.exists(self.grub_default_path):
            return False, "File not found"
            
        with open(self.grub_default_path, 'r') as f:
            lines = f.readlines()
            
        updated_keys = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key = stripped.split("=")[0]
                if key in new_config:
                    lines[i] = f'{key}="{new_config[key]}"\n'
                    updated_keys.add(key)
                    
        for key, val in new_config.items():
            if key not in updated_keys:
                lines.append(f'{key}="{val}"\n')
                
        with open(self.grub_default_path, 'w') as f:
            f.writelines(lines)
            
        if not self.validate_dry_run():
            snapshots = self.backup.list_snapshots()
            if snapshots:
                self.backup.restore_snapshot(snapshots[0])
            return False, "Syntax error detected during dry-run. Reverted to safety."
            
        self.update_grub()
        return True, "Success"

    def set_default_kernel(self, title):
        return self.write_advanced_config({"GRUB_DEFAULT": title})

    def setup_fallback(self):
        config_updates = {
            "GRUB_DEFAULT": "saved",
            "GRUB_SAVEDEFAULT": "true",
            "GRUB_DISABLE_SUBMENU": "y"
        }
        return self.write_advanced_config(config_updates)
        
    def set_kernel_next_boot(self, title):
        try:
            subprocess.run(["grub-reboot", title], check=True)
            return True, f"Next boot set to: {title}"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to set next boot: {e}"
    def generate_custom_entry(self):
        script_content = """#!/bin/sh
exec tail -n +3 $0
# This file provides an easy way to add custom menu entries for fospx-kernel-mgr.
# It searches for installed kernels and adds them to the main menu.

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME="${PRETTY_NAME:-Debian}"
else
    OS_NAME="Linux"
fi

for kern in /boot/vmlinuz-*; do
    version="${kern#/boot/vmlinuz-}"
    initrd="/boot/initrd.img-${version}"
    if [ -f "$initrd" ]; then
        echo "menuentry '${OS_NAME} with ${version} kernel' {"
        echo "    linux   ${kern} root=/dev/mapper/main-root ro quiet" # Simplified, in reality needs actual root UUID
        echo "    initrd  ${initrd}"
        echo "}"
    fi
done
"""
        if os.geteuid() != 0:
            return False, "Root privileges required to generate custom GRUB entries."
            
        try:
            with open(self.custom_script_path, "w") as f:
                f.write(script_content)
                
            os.chmod(self.custom_script_path, 0o755)
            self.update_grub()
            return True, "Custom GRUB entries generated successfully."
        except Exception as e:
            return False, f"Error generating custom entry: {e}"

    def update_grub(self):
        try:
            subprocess.run(["update-grub"], check=True)
            print("GRUB updated successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to update GRUB: {e}")

    def get_grub_entries(self):
        cfg_path = "/boot/grub/grub.cfg"
        entries = []
        if not os.path.exists(cfg_path):
            return entries
            
        try:
            try:
                with open(cfg_path, 'r') as f:
                    lines = f.readlines()
            except PermissionError:
                try:
                    out = subprocess.check_output(["sudo", "-n", "cat", cfg_path], stderr=subprocess.DEVNULL)
                    lines = out.decode('utf-8').split('\n')
                except Exception:
                    try:
                        out = subprocess.check_output(["pkexec", "cat", cfg_path], stderr=subprocess.DEVNULL)
                        lines = out.decode('utf-8').split('\n')
                    except Exception:
                        return [{"title": "Permission Denied: Cannot read /boot/grub/grub.cfg", "type": "menuentry"}]
                
            current_submenu = None
            brace_level = 0
            submenu_brace_level = -1
            
            for line in lines:
                line = line.strip()
                if line.startswith("submenu "):
                    title = line.split("'")[1] if "'" in line else (line.split('"')[1] if '"' in line else line.split()[1])
                    current_submenu = {"title": title, "type": "submenu", "children": []}
                    entries.append(current_submenu)
                    submenu_brace_level = brace_level
                elif line.startswith("menuentry "):
                    title = line.split("'")[1] if "'" in line else (line.split('"')[1] if '"' in line else line.split()[1])
                    item = {"title": title, "type": "menuentry"}
                    if current_submenu:
                        current_submenu["children"].append(item)
                    else:
                        entries.append(item)
                
                if "{" in line:
                    brace_level += line.count("{")
                if "}" in line:
                    brace_level -= line.count("}")
                    if current_submenu and brace_level == submenu_brace_level:
                        current_submenu = None
                        
        except Exception as e:
            print(f"Error parsing GRUB cfg: {e}")
            
        return entries
