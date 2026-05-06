import subprocess
import os
import shutil

class SafetyManager:
    _SNAPSHOT_DEPS = ["timeshift", "btrfs-progs", "kdump-tools"]
    _BUILD_DEPS = [
        "build-essential",
        "flex",
        "bison",
        "libncurses-dev",
        "libssl-dev",
        "libelf-dev",
        "bc",
        "rsync",
    ]

    def __init__(self):
        self.dependencies = self._SNAPSHOT_DEPS + self._BUILD_DEPS

    def check_dependencies(self):
        cmd_map = {
            "timeshift":       "timeshift",
            "btrfs-progs":     "btrfs",
            "kdump-tools":     "kdump-config",
            "build-essential": "gcc",
            "flex":            "flex",
            "bison":           "bison",
            "libncurses-dev":  None,   # dpkg
            "libssl-dev":      None,   # dpkg
            "libelf-dev":      None,   # dpkg
            "bc":              "bc",
            "rsync":           "rsync",
        }
        missing = []
        for dep in self.dependencies:
            binary = cmd_map.get(dep, dep)
            if binary is None:
                try:
                    result = subprocess.run(
                        ["dpkg-query", "-W", "-f=${Status}", dep],
                        capture_output=True, text=True
                    )
                    if "install ok installed" not in result.stdout:
                        missing.append(dep)
                except Exception:
                    missing.append(dep)
            else:
                if shutil.which(binary) is None:
                    missing.append(dep)
        return missing

    def install_dependencies(self):
        missing = self.check_dependencies()
        if not missing:
            return True, "All dependencies are already installed."
        if os.geteuid() != 0:
            return False, "Root privileges required to install dependencies."
        try:
            cmd = ["apt-get", "update"]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cmd = ["apt-get", "install", "-y"] + missing
            subprocess.run(cmd, check=True)
            return True, f"Successfully installed: {', '.join(missing)}"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to install dependencies: {e}"

    def create_snapshot(self, description="Before Kernel Update"):
        if shutil.which("timeshift") is None:
            return False, "Timeshift is not installed."
        if os.geteuid() != 0:
            return False, "Root privileges required to create snapshot."
        try:
            cmd = ["timeshift", "--create", "--comments", description, "--tags", "O"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, "Snapshot created successfully."
        except subprocess.CalledProcessError as e:
            return False, f"Failed to create snapshot: {e.stderr or e.stdout}"

    def analyze_panic(self):
        logs = []
        pstore_dir = "/sys/fs/pstore"
        if os.path.exists(pstore_dir):
            try:
                for filename in os.listdir(pstore_dir):
                    if "dmesg" in filename or "console" in filename:
                        filepath = os.path.join(pstore_dir, filename)
                        with open(filepath, "r", errors="ignore") as f:
                            logs.append(f"--- pstore: {filename} ---\n" + f.read()[:2000] + "\n...")
            except Exception as e:
                logs.append(f"Error reading pstore: {e}")
        else:
            logs.append("pstore directory not found (/sys/fs/pstore).")
            
        crash_dir = "/var/crash"
        if os.path.exists(crash_dir):
            try:
                crash_dirs = [d for d in os.listdir(crash_dir) if os.path.isdir(os.path.join(crash_dir, d))]
                if crash_dirs:
                    logs.append(f"Found kdump crash directories: {', '.join(crash_dirs)}")
                    logs.append("Use 'crash' utility to analyze these vmcores.")
                else:
                    logs.append("No kdump crash directories found in /var/crash.")
            except Exception as e:
                logs.append(f"Error reading /var/crash: {e}")
        else:
            logs.append("kdump directory not found (/var/crash).")
            
        if not logs:
            return "No panic logs found."
            
        return "\n\n".join(logs)
