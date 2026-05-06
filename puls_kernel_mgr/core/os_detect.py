import platform

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

def is_gtk4_supported():
    os_info = parse_os_release()
    os_id = os_info.get("ID", "").lower()
    version_id = os_info.get("VERSION_ID", "")
    
    if os_id == "ubuntu":
        try:
            major_version = float(version_id)
            if major_version < 22.04:
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
