import subprocess
import os
import requests
from bs4 import BeautifulSoup
import re
import shutil
import tempfile
import glob
import time
import json


class KernelManager:
    def __init__(self):
        self.download_dir = "/usr/src"
        self.mirror_base = "https://mirrors.edge.kernel.org/pub/linux/kernel/"
        self.zen_repo_api = "https://api.github.com/repos/zen-kernel/zen-kernel/tags?per_page=100"
        self.prebuilt_builds_url = "https://prebuiltkernels.com/builds"
        self.prebuilt_home_url = "https://prebuiltkernels.com/"

    def fetch_zen_kernels(self):
        """Fetch available Linux-Zen kernel releases across multiple pages."""
        zen_kernels = []
        try:
            for page in range(1, 4):
                url = f"https://api.github.com/repos/zen-kernel/zen-kernel/tags?per_page=100&page={page}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    tags = resp.json()
                    if not tags:
                        break
                    for t in tags:
                        name = t.get("name", "")
                        ver = name[1:] if name.startswith("v") else name
                        tar_url = f"https://github.com/zen-kernel/zen-kernel/archive/refs/tags/{name}.tar.gz"
                        zen_kernels.append({
                            "version": ver,
                            "moniker": "zen",
                            "iseol": False,
                            "source": tar_url,
                            "pgp": None,
                            "kernel_type": "zen",
                        })
                else:
                    break
        except Exception as e:
            print(f"Error fetching Linux-Zen kernels: {e}")
        return zen_kernels

    def fetch_prebuilt_kernels(self):
        """Fetch all prebuilt DEB kernel packages across all pages of prebuiltkernels.com."""
        prebuilt_kernels = []
        for page in range(1, 30):
            try:
                url = f"https://prebuiltkernels.com/builds/page/{page}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    try:
                        items = resp.json()
                        if not items:
                            break
                        for item in items:
                            ver = item.get("version")
                            img_fn = item.get("linux_image_filename")
                            hdr_fn = item.get("linux_headers_filename")
                            moniker = item.get("moniker", "prebuilt")
                            if ver and img_fn and hdr_fn:
                                deb_urls = [
                                    f"https://prebuiltkernels.com/download/{img_fn}",
                                    f"https://prebuiltkernels.com/download/{hdr_fn}",
                                ]
                                prebuilt_kernels.append({
                                    "version": ver,
                                    "moniker": moniker,
                                    "iseol": (moniker == "eol"),
                                    "deb_urls": deb_urls,
                                    "kernel_type": "prebuilt",
                                })
                    except Exception:
                        break
                else:
                    break
            except Exception as e:
                print(f"Error fetching prebuilt kernels page {page}: {e}")
                break
        return prebuilt_kernels

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
                            "iseol": release.get("iseol", False),
                        }
        except Exception as e:
            print(f"Error fetching JSON metadata: {e}")

        for major in ["v7.x", "v6.x", "v5.x"]:
            try:
                url = f"{self.mirror_base}{major}/"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.find_all("a"):
                    href = link.get("href")
                    match = re.match(
                        r"^linux-(\d+\.\d+(?:\.\d+)?(?:-rc\d+)?)\.tar\.xz$", href
                    )
                    if match:
                        full_version = match.group(1)
                        parts = full_version.replace("-rc", ".").split(".")
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
                                "pgp": f"{self.mirror_base}{major}/linux-{full_version}.tar.sign",
                                "kernel_type": "mainline",
                            }
                            if not any(
                                k["version"] == full_version for k in kernels[series]
                            ):
                                kernels[series].append(k_info)
            except Exception as e:
                print(f"Error fetching from {major}: {e}")

        import platform

        host_release = platform.release()
        match = re.match(r"^(\d+\.\d+)", host_release)
        min_kernel_parts = [0, 0]
        if match:
            min_kernel_parts = [int(x) for x in match.group(1).split(".")]

        filtered_kernels = {}
        sorted_series = sorted(
            kernels.keys(),
            key=lambda s: [int(x) for x in s.split(".")],
            reverse=True,
        )

        for series in sorted_series:
            versions = kernels[series]
            s_parts = [int(x) for x in series.split(".")]
            if s_parts[0] > min_kernel_parts[0] or (
                s_parts[0] == min_kernel_parts[0]
                and s_parts[1] >= min_kernel_parts[1]
            ):

                def v_sort(v_info):
                    v_str = v_info["version"].replace("-rc", ".0.")
                    return [int(u) for u in v_str.split(".") if u.isdigit()]

                versions.sort(key=v_sort, reverse=True)
                filtered_kernels[series] = versions

        # Add Linux-Zen category
        zen_list = self.fetch_zen_kernels()
        if zen_list:
            filtered_kernels["Linux-Zen"] = zen_list

        # Add Prebuilt DEB category
        prebuilt_list = self.fetch_prebuilt_kernels()
        if prebuilt_list:
            filtered_kernels["Prebuilt DEB (prebuiltkernels.com)"] = prebuilt_list

        return filtered_kernels

    def get_installed_kernels(self):
        kernels = []
        for file in glob.glob("/boot/vmlinuz-*"):
            version = os.path.basename(file).replace("vmlinuz-", "")
            kernels.append(version)

        def version_key(v):
            parts = []
            for p in v.replace("-", ".").split("."):
                try:
                    parts.append(int(p))
                except Exception:
                    parts.append(0)
            return parts

        return sorted(kernels, key=version_key, reverse=True)

    def check_boot_space(self, required_mb=350):
        try:
            stat = shutil.disk_usage("/boot")
            free_mb = stat.free // (1024 * 1024)
            return free_mb >= required_mb, free_mb
        except Exception:
            return True, -1

    def download_and_extract(self, version, source_url=None, pgp_url=None):
        if not source_url:
            major = "v6.x" if version.startswith("6.") else "v5.x"
            source_url = f"{self.mirror_base}{major}/linux-{version}.tar.xz"
            pgp_url = f"{self.mirror_base}{major}/linux-{version}.tar.sign"

        ext = ".tar.gz" if source_url.endswith(".tar.gz") else ".tar.xz"
        tarball_path = os.path.join(self.download_dir, f"kernel-{version}{ext}")
        sign_path = os.path.join(self.download_dir, f"kernel-{version}.tar.sign")

        print(f"Downloading {source_url}...")
        try:
            with requests.get(source_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(tarball_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded * 100 // total
                            dl_mb = downloaded // (1024 * 1024)
                            total_mb = total // (1024 * 1024)
                            print(
                                f"\rDownloading... {dl_mb}/{total_mb} MB ({pct}%)",
                                end="",
                                flush=True,
                            )
            print()
        except Exception as e:
            print(f"Streaming download failed ({e}), falling back to wget...")
            subprocess.run(
                ["wget", "-q", "--show-progress", "-O", tarball_path, source_url],
                check=True,
            )

        before_dirs = set(
            os.path.join(self.download_dir, d)
            for d in os.listdir(self.download_dir)
            if os.path.isdir(os.path.join(self.download_dir, d))
        )

        if pgp_url:
            print("Downloading signature...")
            subprocess.run(["wget", "-q", "-O", sign_path, pgp_url], check=True)
            print("Verifying GPG signature...")
            tar_path = tarball_path.replace(".xz", "")
            subprocess.run(["xz", "-d", "-k", tarball_path], check=True)
            try:
                subprocess.run(
                    ["gpg", "--verify", sign_path, tar_path],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                print(
                    "Signature verification failed or keys missing. "
                    "Fetching developer keys..."
                )
                for fp in [
                    "647F28654894E3BD457199BE38DBBDC86092693E",
                    "ABAF11C65A2970B130ABE3C479BE3E4300411886",
                    "AC2B29BD34A6AFDDB3F68F35E7BFC8EC95861109",
                ]:
                    subprocess.run(
                        [
                            "gpg",
                            "--keyserver",
                            "hkps://keyserver.ubuntu.com",
                            "--recv-keys",
                            fp,
                        ],
                        check=False,
                    )
                subprocess.run(
                    ["gpg", "--verify", sign_path, tar_path], check=True
                )

            print("GPG Signature Verified Successfully.")
            print(f"Extracting {tar_path}...")
            subprocess.run(
                ["tar", "-xf", tar_path, "-C", self.download_dir], check=True
            )
            os.remove(tar_path)
        else:
            print("Extracting kernel tarball...")
            flag = "-xzvf" if ext == ".tar.gz" else "-xJf"
            subprocess.run(
                ["tar", flag, tarball_path, "-C", self.download_dir], check=True
            )

        after_dirs = set(
            os.path.join(self.download_dir, d)
            for d in os.listdir(self.download_dir)
            if os.path.isdir(os.path.join(self.download_dir, d))
        )

        new_dirs = list(after_dirs - before_dirs)
        target_dir = os.path.join(self.download_dir, f"linux-{version}")

        if new_dirs:
            extracted_folder = new_dirs[0]
            if extracted_folder != target_dir:
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir, ignore_errors=True)
                os.rename(extracted_folder, target_dir)
        elif not os.path.exists(target_dir):
            for entry in os.listdir(self.download_dir):
                full_entry = os.path.join(self.download_dir, entry)
                if os.path.isdir(full_entry) and version in entry:
                    target_dir = full_entry
                    break
        return target_dir

    def install_prebuilt_kernel(self, version, deb_urls):
        if os.geteuid() != 0:
            raise PermissionError("Root privileges required to install kernel packages.")

        print(f"Downloading prebuilt kernel package(s) for version {version}...")
        download_tmp = tempfile.mkdtemp(prefix="prebuilt_kernel_")
        downloaded_debs = []
        try:
            for url in deb_urls:
                fname = os.path.basename(url)
                dest = os.path.join(download_tmp, fname)
                print(f"Downloading {url}...")
                subprocess.run(["wget", "-q", "--show-progress", "-O", dest, url], check=True)
                downloaded_debs.append(dest)

            if downloaded_debs:
                print("Installing prebuilt DEB kernel package(s) via APT/dpkg...")
                try:
                    subprocess.run(["apt-get", "install", "-y"] + downloaded_debs, check=True)
                except subprocess.CalledProcessError:
                    subprocess.run(["dpkg", "-i"] + downloaded_debs, check=True)
                    subprocess.run(["apt-get", "install", "-f", "-y"], check=True)

                self.run_dkms(version)
                print(f"Prebuilt kernel {version} installed successfully!")
            else:
                raise ValueError("No deb URLs provided or downloaded.")
        finally:
            shutil.rmtree(download_tmp, ignore_errors=True)

    def compile_and_install(self, version, use_menuconfig=False):
        if os.geteuid() != 0:
            raise PermissionError("You must run this as root to install a kernel.")

        source_url = None
        pgp_url = None
        kernel_type = "mainline"
        deb_urls = []
        if isinstance(version, dict):
            source_url = version.get("source")
            pgp_url = version.get("pgp")
            kernel_type = version.get("kernel_type", "mainline")
            deb_urls = version.get("deb_urls", [])
            version = version.get("version")

        if kernel_type == "prebuilt" or deb_urls:
            return self.install_prebuilt_kernel(version, deb_urls)

        ok, free_mb = self.check_boot_space()
        if not ok:
            print(
                f"WARNING: /boot only has {free_mb} MB free. "
                "At least 350 MB is recommended. Proceeding anyway..."
            )

        from puls_kernel_mgr.core.safety import SafetyManager

        print("Verifying and installing build dependencies...")
        SafetyManager().install_dependencies()

        src_dir = self.download_and_extract(version, source_url, pgp_url)

        print(f"Configuring tailored kernel {version} using localmodconfig...")
        current_kernel = os.uname().release
        config_path = f"/boot/config-{current_kernel}"
        if os.path.exists(config_path):
            subprocess.run(
                ["cp", config_path, os.path.join(src_dir, ".config")], check=True
            )

        # Disable signing keys and BTF debug info BEFORE olddefconfig to avoid interactive prompts
        for cfg_cmd in [
            ["scripts/config", "--set-str", "SYSTEM_TRUSTED_KEYS", ""],
            ["scripts/config", "--set-str", "SYSTEM_REVOCATION_KEYS", ""],
            ["scripts/config", "--set-str", "MODULE_SIG_KEY", ""],
            ["scripts/config", "--disable", "SYSTEM_TRUSTED_KEYS"],
            ["scripts/config", "--disable", "SYSTEM_REVOCATION_KEYS"],
            ["scripts/config", "--disable", "MODULE_SIG_KEY"],
            ["scripts/config", "--disable", "MODULE_SIG"],
            ["scripts/config", "--disable", "DEBUG_INFO_BTF"],
        ]:
            subprocess.run(cfg_cmd, cwd=src_dir, check=False)

        subprocess.run("yes '' | make olddefconfig", shell=True, cwd=src_dir, check=True)
        subprocess.run("yes '' | make localmodconfig", shell=True, cwd=src_dir, check=True)

        from puls_kernel_mgr.core.kconfig import KconfigManager

        kconf = KconfigManager(src_dir)
        if use_menuconfig:
            print("Launching make menuconfig in external terminal...")
            success, msg = kconf.launch_menuconfig()
            if not success:
                print(f"Warning: menuconfig failed: {msg}")

        env = kconf.set_reproducible_build_env()
        build_start_time = time.time() - 10
        nproc = str(os.cpu_count() or 1)
        print(f"Building Debian (.deb) kernel packages for {version} with {nproc} threads using bindeb-pkg...")
        try:
            subprocess.run(
                f"yes '' | make -j {nproc} bindeb-pkg",
                shell=True,
                cwd=src_dir,
                env=env,
                check=True,
            )
        except subprocess.CalledProcessError:
            print("bindeb-pkg failed, attempting with fakeroot...")
            subprocess.run(
                f"yes '' | fakeroot make -j {nproc} bindeb-pkg",
                shell=True,
                cwd=src_dir,
                env=env,
                check=True,
            )

        parent_dir = os.path.dirname(src_dir.rstrip("/"))
        deb_files = glob.glob(os.path.join(parent_dir, "*.deb"))
        ver_clean = str(version).lstrip("v")
        target_debs = [
            f
            for f in deb_files
            if ("linux-image-" in f or "linux-headers-" in f)
            and ver_clean in os.path.basename(f)
            and os.path.getmtime(f) >= build_start_time
        ]

        has_image_deb = any("linux-image-" in f for f in target_debs)
        if not target_debs or not has_image_deb:
            print(
                f"Warning: bindeb-pkg did not produce a complete linux-image deb package for {version}. "
                "Falling back to standard make modules_install & make install..."
            )
            subprocess.run(["make", "-j", nproc, "modules_install"], cwd=src_dir, env=env, check=True)
            subprocess.run(["make", "install"], cwd=src_dir, env=env, check=True)
        else:
            print(
                f"Installing generated package(s): {[os.path.basename(d) for d in target_debs]} via APT/dpkg..."
            )
            try:
                subprocess.run(["apt-get", "install", "-y"] + target_debs, check=True)
            except subprocess.CalledProcessError:
                print("apt-get install failed, installing via dpkg -i...")
                subprocess.run(["dpkg", "-i"] + target_debs, check=True)
                subprocess.run(["apt-get", "install", "-f", "-y"], check=True)

        self.run_dkms(version)
        print("Kernel compilation and package-managed installation complete!")

    def remove_kernel(self, version_string):
        if os.geteuid() != 0:
            raise PermissionError("Root privileges required to remove a kernel.")

        current = os.uname().release
        if current == version_string:
            raise ValueError(
                f"Cannot remove the currently running kernel ({version_string}). "
                "Please boot into another kernel first."
            )

        print(f"Searching for package-managed kernel matching version {version_string}...")
        pkg_pattern = f"linux-image-*{version_string}*"
        installed_pkgs = []
        try:
            res = subprocess.run(
                ["dpkg-query", "-W", "-f=${Package}\n", pkg_pattern],
                capture_output=True,
                text=True,
                check=False,
            )
            installed_pkgs = [p.strip() for p in res.stdout.splitlines() if p.strip()]

            res_hdr = subprocess.run(
                [
                    "dpkg-query",
                    "-W",
                    "-f=${Package}\n",
                    f"linux-headers-*{version_string}*",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            installed_pkgs.extend(
                [p.strip() for p in res_hdr.stdout.splitlines() if p.strip()]
            )
        except Exception as e:
            print(f"Error querying dpkg: {e}")

        if installed_pkgs:
            print(f"Removing packages via APT: {', '.join(installed_pkgs)}...")
            try:
                subprocess.run(["apt-get", "purge", "-y"] + installed_pkgs, check=True)
                print(f"Package-managed kernel {version_string} purged successfully!")
                return
            except subprocess.CalledProcessError as e:
                print(f"apt-get purge error ({e}), performing fallback cleanup...")

        print(f"Performing legacy file cleanup for un-packaged kernel {version_string}...")
        files_to_remove = [
            f"/boot/vmlinuz-{version_string}",
            f"/boot/initrd.img-{version_string}",
            f"/boot/config-{version_string}",
            f"/boot/System.map-{version_string}",
        ]

        for f in files_to_remove:
            if os.path.exists(f):
                os.remove(f)
                print(f"  Removed {f}")
            else:
                print(f"  Not found (skipping): {f}")

        mod_dir = f"/lib/modules/{version_string}"
        if os.path.isdir(mod_dir):
            shutil.rmtree(mod_dir)
            print(f"  Removed {mod_dir}")

        print("Updating GRUB...")
        try:
            subprocess.run(["update-grub"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: update-grub failed: {e}")

        print(f"Kernel {version_string} removed successfully.")

    def run_dkms(self, kernel_version):
        try:
            print(f"Running DKMS for kernel {kernel_version}...")
            subprocess.run(
                ["dkms", "autoinstall", "-k", kernel_version], check=True
            )
            print("DKMS completed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"DKMS error (non-fatal): {e}")
