import os
import shutil
import time
from datetime import datetime

class GrubBackupManager:
    def __init__(self):
        self.backup_dir = "/var/backups/fospx-grub"
        self.default_grub = "/etc/default/grub"
        self.grub_d = "/etc/grub.d"
        
        if os.geteuid() == 0 and not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)
            
    def create_snapshot(self):
        if os.geteuid() != 0:
            return False, "Root privileges required for snapshot."
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = os.path.join(self.backup_dir, f"snapshot_{timestamp}")
        os.makedirs(snapshot_path, exist_ok=True)
        
        try:
            if os.path.exists(self.default_grub):
                shutil.copy2(self.default_grub, os.path.join(snapshot_path, "grub_default"))
                
            if os.path.exists(self.grub_d):
                shutil.copytree(self.grub_d, os.path.join(snapshot_path, "grub.d"), dirs_exist_ok=True)
                
            return True, snapshot_path
        except Exception as e:
            return False, str(e)
            
    def list_snapshots(self):
        if not os.path.exists(self.backup_dir):
            return []
            
        snapshots = [d for d in os.listdir(self.backup_dir) if d.startswith("snapshot_")]
        snapshots.sort(reverse=True)
        return snapshots
        
    def restore_snapshot(self, snapshot_name):
        if os.geteuid() != 0:
            return False, "Root privileges required to restore."
            
        snapshot_path = os.path.join(self.backup_dir, snapshot_name)
        if not os.path.exists(snapshot_path):
            return False, "Snapshot not found."
            
        try:
            src_grub = os.path.join(snapshot_path, "grub_default")
            if os.path.exists(src_grub):
                shutil.copy2(src_grub, self.default_grub)
                
            src_grub_d = os.path.join(snapshot_path, "grub.d")
            if os.path.exists(src_grub_d):
                shutil.rmtree(self.grub_d)
                shutil.copytree(src_grub_d, self.grub_d)
                
            return True, "Restored successfully. Please run update-grub."
        except Exception as e:
            return False, str(e)
