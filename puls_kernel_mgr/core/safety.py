import subprocess
import os
import shutil
from puls_kernel_mgr.core.os_detect import get_distro_info


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
        "wget",
    ]

    _CMD_MAP = {
        "timeshift":       "timeshift",
        "btrfs-progs":     "btrfs",
        "kdump-tools":     "kdump-config",
        "build-essential": "gcc",
        "flex":            "flex",
        "bison":           "bison",
        "libncurses-dev":  None,   # dpkg only
        "libssl-dev":      None,   # dpkg only
        "libelf-dev":      None,   # dpkg only
        "bc":              "bc",
        "rsync":           "rsync",
        "wget":            "wget",
    }

    def __init__(self):
        self.dependencies = self._SNAPSHOT_DEPS + self._BUILD_DEPS


    def check_single_dependency(self, dep):
        binary = self._CMD_MAP.get(dep, dep)
        if binary is None:
            try:
                result = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Status}", dep],
                    capture_output=True,
                    text=True,
                )
                return "install ok installed" in result.stdout
            except Exception:
                return False
        return shutil.which(binary) is not None

    def check_dependencies(self):
        return [d for d in self.dependencies if not self.check_single_dependency(d)]

    def get_dependency_status(self):
        return {d: self.check_single_dependency(d) for d in self.dependencies}

    def install_dependencies(self):
        distro = get_distro_info()
        pkg_manager = distro.get("pkg_manager", "apt")

        if pkg_manager not in ("apt", "apt-get"):
            return (
                False,
                f"Unsupported package manager '{pkg_manager}'. "
                "Only Debian/Ubuntu (apt) systems are currently supported.",
            )

        missing = self.check_dependencies()
        if not missing:
            print("All dependencies are already installed.")
            return True, "All dependencies are already installed."
        if os.geteuid() != 0:
            return False, "Root privileges required to install dependencies."
        try:
            subprocess.run(
                ["apt-get", "update"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(["apt-get", "install", "-y"] + missing, check=True)
            return True, f"Successfully installed: {', '.join(missing)}"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to install dependencies: {e}"

    def check_boot_space(self, required_mb=350):
        try:
            stat = shutil.disk_usage("/boot")
            free_mb = stat.free // (1024 * 1024)
            return free_mb >= required_mb, free_mb
        except Exception:
            return True, -1

    def create_snapshot(self, description="Before Kernel Update"):
        if shutil.which("timeshift") is None:
            return False, "Timeshift is not installed."
        if os.geteuid() != 0:
            return False, "Root privileges required to create snapshot."
        try:
            cmd = [
                "timeshift",
                "--create",
                "--comments",
                description,
                "--tags",
                "O",
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, "Snapshot created successfully."
        except subprocess.CalledProcessError as e:
            return False, f"Failed to create snapshot: {e.stderr or e.stdout}"

    def list_timeshift_snapshots(self):
        if shutil.which("timeshift") is None:
            return []
        try:
            result = subprocess.run(
                ["timeshift", "--list", "--scripted"],
                capture_output=True,
                text=True,
            )
            snapshots = []
            for line in result.stdout.splitlines():
                parts = line.strip().split(None, 4)
                if len(parts) >= 3 and parts[0].isdigit():
                    snapshots.append({
                        "num": parts[0],
                        "date": parts[2] if len(parts) > 2 else "?",
                        "tags": parts[3] if len(parts) > 3 else "",
                        "desc": parts[4] if len(parts) > 4 else "",
                    })
            return snapshots
        except Exception as e:
            return []

    def analyze_panic(self):
        logs = []
        pstore_dir = "/sys/fs/pstore"
        if os.path.exists(pstore_dir):
            try:
                for filename in os.listdir(pstore_dir):
                    if "dmesg" in filename or "console" in filename:
                        filepath = os.path.join(pstore_dir, filename)
                        with open(filepath, "r", errors="ignore") as f:
                            logs.append(
                                f"--- pstore: {filename} ---\n"
                                + f.read()[:2000]
                                + "\n..."
                            )
            except Exception as e:
                logs.append(f"Error reading pstore: {e}")
        else:
            logs.append("pstore directory not found (/sys/fs/pstore).")

        crash_dir = "/var/crash"
        if os.path.exists(crash_dir):
            try:
                crash_dirs = [
                    d
                    for d in os.listdir(crash_dir)
                    if os.path.isdir(os.path.join(crash_dir, d))
                ]
                if crash_dirs:
                    logs.append(
                        f"Found kdump crash directories: {', '.join(crash_dirs)}"
                    )
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
