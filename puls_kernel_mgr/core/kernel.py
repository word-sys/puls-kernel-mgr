import subprocess
import os
import requests
from bs4 import BeautifulSoup
import re

class KernelManager:
    def __init__(self):
        self.download_dir = "/usr/src"
        self.mirror_base = "https://mirrors.edge.kernel.org/pub/linux/kernel/"
        
    def fetch_available_kernels(self):
        kernels = {}
        metadata = {}
        try:
            url = "https://www.kernel.org/releases.json"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for release in data.get("releases", []):
                    ver = release.get("version")
                    if ver:
                        metadata[ver] = {
                            "moniker": release.get("moniker", "unknown"),
                            "iseol": release.get("iseol", False)
                        }
        except Exception as e:
            print(f"Error fetching JSON metadata: {e}")
        for major in ["v7.x", "v6.x", "v5.x"]:
            try:
                url = f"{self.mirror_base}{major}/"
                from bs4 import BeautifulSoup
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                for link in soup.find_all('a'):
                    href = link.get('href')
                    match = re.match(r'^linux-(\d+\.\d+(?:\.\d+)?(?:-rc\d+)?)\.tar\.xz$', href)
                    if match:
                        full_version = match.group(1)
                        parts = full_version.replace('-rc', '.').split('.')
                        if len(parts) >= 2:
                            series = f"{parts[0]}.{parts[1]}"
                            if series not in kernels:
                                kernels[series] = []
                            meta = metadata.get(full_version, {})
                            k_info = {
                                "version": full_version,
                                "moniker": meta.get("moniker", "stable"),
                                "iseol": meta.get("iseol", False),
                                "source": f"{self.mirror_base}{major}/linux-{full_version}.tar.xz",
                                "pgp": f"{self.mirror_base}{major}/linux-{full_version}.tar.sign"
                            }
                            if not any(k['version'] == full_version for k in kernels[series]):
                                kernels[series].append(k_info)
            except Exception as e:
                print(f"Error fetching from {major}: {e}")
        import platform
        host_release = platform.release()
        match = re.match(r'^(\d+\.\d+)', host_release)
        min_kernel_parts = [0, 0]
        if match:
            min_kernel_parts = [int(x) for x in match.group(1).split('.')]
            
        filtered_kernels = {}
        sorted_series = sorted(kernels.keys(), key=lambda s: [int(x) for x in s.split('.')], reverse=True)
        
        for series in sorted_series:
            versions = kernels[series]
            s_parts = [int(x) for x in series.split('.')]
            if s_parts[0] > min_kernel_parts[0] or (s_parts[0] == min_kernel_parts[0] and s_parts[1] >= min_kernel_parts[1]):
                def v_sort(v_info):
                    v_str = v_info['version'].replace('-rc', '.0.')
                    return [int(u) for u in v_str.split('.') if u.isdigit()]
                versions.sort(key=v_sort, reverse=True)
                filtered_kernels[series] = versions
                
        return filtered_kernels

    def get_installed_kernels(self):
        import glob
        import os
        kernels = []
        for file in glob.glob("/boot/vmlinuz-*"):
            version = os.path.basename(file).replace("vmlinuz-", "")
            kernels.append(version)
        def version_key(v):
            parts = []
            for p in v.replace("-", ".").split("."):
                try:
                    parts.append(int(p))
                except:
                    parts.append(0)
            return parts
        return sorted(kernels, key=version_key, reverse=True)
        
    def download_and_extract(self, version, source_url=None, pgp_url=None):
        if not source_url:
            major = "v6.x" if version.startswith("6.") else "v5.x"
            source_url = f"{self.mirror_base}{major}/linux-{version}.tar.xz"
            pgp_url = f"{self.mirror_base}{major}/linux-{version}.tar.sign"
            
        tarball_path = os.path.join(self.download_dir, f"linux-{version}.tar.xz")
        sign_path = os.path.join(self.download_dir, f"linux-{version}.tar.sign")
        
        print(f"Downloading {source_url} to {tarball_path}...")
        subprocess.run(["wget", "-q", "-O", tarball_path, source_url], check=True)
        
        if pgp_url:
            print(f"Downloading signature {pgp_url}...")
            subprocess.run(["wget", "-q", "-O", sign_path, pgp_url], check=True)
            
            print("Verifying GPG signature...")
            tar_path = tarball_path.replace(".xz", "")
            subprocess.run(["xz", "-d", "-k", tarball_path], check=True)
            try:
                subprocess.run(["gpg", "--verify", sign_path, tar_path], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print("Signature verification failed or keys missing. Attempting to fetch developer keys...")
                subprocess.run(["gpg", "--keyserver", "hkp://keyserver.ubuntu.com", "--recv-keys", "647F28654894E3BD457199BE38DBBDC86092693E"], check=False)
                subprocess.run(["gpg", "--keyserver", "hkp://keyserver.ubuntu.com", "--recv-keys", "ABAF11C65A2970B130ABE3C479BE3E4300411886"], check=False)
                
                # Try again
                subprocess.run(["gpg", "--verify", sign_path, tar_path], check=True)
                
            print("GPG Signature Verified Successfully.")
            print(f"Extracting {tar_path}...")
            subprocess.run(["tar", "-xf", tar_path, "-C", self.download_dir], check=True)
            os.remove(tar_path)
        else:
            print("Warning: No PGP signature URL provided. Skipping verification.")
            print(f"Extracting {tarball_path}...")
            subprocess.run(["tar", "-xf", tarball_path, "-C", self.download_dir], check=True)
            
        return os.path.join(self.download_dir, f"linux-{version}")

    def compile_and_install(self, version, use_menuconfig=False):
        if os.geteuid() != 0:
            raise PermissionError("You must run this as root to install a kernel.")
            
        source_url = None
        pgp_url = None
        if isinstance(version, dict):
            source_url = version.get("source")
            pgp_url = version.get("pgp")
            version = version.get("version")
            
        src_dir = self.download_and_extract(version, source_url, pgp_url)
        
        print(f"Configuring tailored kernel {version} using localmodconfig...")
        current_kernel = os.uname().release
        config_path = f"/boot/config-{current_kernel}"
        if os.path.exists(config_path):
            subprocess.run(["cp", config_path, os.path.join(src_dir, ".config")], check=True)
            
        subprocess.run(["make", "olddefconfig"], cwd=src_dir, check=True)
        subprocess.run("yes '' | make localmodconfig", shell=True, cwd=src_dir, check=True)
        subprocess.run(["scripts/config", "--set-str", "SYSTEM_TRUSTED_KEYS", ""], cwd=src_dir, check=True)
        subprocess.run(["scripts/config", "--set-str", "SYSTEM_REVOCATION_KEYS", ""], cwd=src_dir, check=True)
        subprocess.run(["scripts/config", "--disable", "DEBUG_INFO_BTF"], cwd=src_dir, check=True)
        subprocess.run(["scripts/config", "--disable", "MODULE_SIG_KEY"], cwd=src_dir, check=True)
        
        from fospx_kernel_mgr.core.kconfig import KconfigManager
        kconf = KconfigManager(src_dir)
        if use_menuconfig:
            print("Launching make menuconfig in external terminal...")
            success, msg = kconf.launch_menuconfig()
            if not success:
                print(f"Warning: menuconfig failed: {msg}")
                
        env = kconf.set_reproducible_build_env()
        print("Compiling kernel... This may take a while.")
        nproc = str(os.cpu_count() or 1)
        subprocess.run(["make", "-j", nproc], cwd=src_dir, env=env, check=True)
        
        print("Installing modules...")
        subprocess.run(["make", "modules_install"], cwd=src_dir, env=env, check=True)
        
        print("Installing kernel...")
        subprocess.run(["make", "install"], cwd=src_dir, env=env, check=True)
        
        self.run_dkms(version)
        print("Kernel compilation and installation complete!")
        
    def run_dkms(self, kernel_version):
        try:
            print(f"Running DKMS for kernel {kernel_version}...")
            subprocess.run(["dkms", "autoinstall", "-k", kernel_version], check=True)
            print("DKMS completed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"DKMS error: {e}")
            
