import platform
import shutil


def parse_os_release():
    os_info = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    os_info[key] = val.strip('"\'')
    except Exception:
        pass
    return os_info


def get_distro_info():
    os_info = parse_os_release()
    os_id = os_info.get("ID", "").lower()
    id_like = os_info.get("ID_LIKE", "").lower()

    if shutil.which("apt-get") or os_id in ("debian", "ubuntu") or "debian" in id_like or "ubuntu" in id_like:
        pkg_manager = "apt"
    elif shutil.which("dnf"):
        pkg_manager = "dnf"
    elif shutil.which("pacman"):
        pkg_manager = "pacman"
    elif shutil.which("zypper"):
        pkg_manager = "zypper"
    else:
        pkg_manager = "unknown"

    os_info["pkg_manager"] = pkg_manager
    os_info["os_id"] = os_id
    return os_info


def is_gtk4_supported():
    os_info = parse_os_release()
    os_id = os_info.get("ID", "").lower()
    version_id = os_info.get("VERSION_ID", "")

    if os_id == "ubuntu":
        try:
            if float(version_id) < 22.04:
                return False
        except ValueError:
            pass

    if os_id == "debian":
        try:
            if version_id and int(version_id) < 12:
                return False
        except ValueError:
            pass

    return True


def is_apt_based():
    info = get_distro_info()
    return info.get("pkg_manager", "unknown") in ("apt", "apt-get")
