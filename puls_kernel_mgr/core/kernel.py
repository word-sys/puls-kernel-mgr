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
import hashlib
import platform
from urllib.parse import urljoin


class KernelManager:
    def __init__(self):
        self.download_dir = "/usr/src"
        self.mirror_base = "https://mirrors.edge.kernel.org/pub/linux/kernel/"
        self.zen_repo_api = "https://api.github.com/repos/zen-kernel/zen-kernel/tags?per_page=100"
        self.prebuilt_builds_url = "https://prebuiltkernels.com/builds"
        self.prebuilt_home_url = "https://prebuiltkernels.com/"
        self.ubuntu_mainline_base = "https://kernel.ubuntu.com/mainline/"

    @staticmethod
    def _version_sort_key(version_str):
        """Return a comparable tuple so e.g. 7.3.5 > 7.3 > 7.3-rc7 > 7.3-rc1."""
        ver = str(version_str).lstrip("v")
        rc_match = re.search(r"-rc(\d+)$", ver)
        is_release = 0 if rc_match else 1
        rc_num = int(rc_match.group(1)) if rc_match else 0
        base = ver[:rc_match.start()] if rc_match else ver
        nums = [int(p) for p in re.split(r"[^0-9]+", base) if p.isdigit()]
        while len(nums) < 3:
            nums.append(0)
        return (nums[0], nums[1], nums[2], is_release, rc_num)

    def _detect_debian_arch(self):
        """Return the Debian/Ubuntu architecture name (e.g. amd64, arm64)."""
        try:
            res = subprocess.run(
                ["dpkg", "--print-architecture"],
                capture_output=True,
                text=True,
                check=True,
            )
            arch = res.stdout.strip()
            if arch:
                return arch
        except Exception:
            pass

        machine = platform.machine().lower()
        arch_map = {
            "x86_64": "amd64",
            "amd64": "amd64",
            "aarch64": "arm64",
            "arm64": "arm64",
            "armv7l": "armhf",
            "armv7hl": "armhf",
            "ppc64le": "ppc64el",
            "s390x": "s390x",
            "riscv64": "riscv64",
            "i386": "i386",
            "i686": "i386",
        }
        return arch_map.get(machine, machine)

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

    def fetch_ubuntu_mainline_kernels(self, metadata=None, min_kernel_parts=None):
        """Fetch available Ubuntu mainline kernel releases from kernel.ubuntu.com/mainline/."""
        ubuntu_kernels = []
        metadata = metadata or {}
        if min_kernel_parts is None:
            host_release = platform.release()
            match = re.match(r"^(\d+\.\d+)", host_release)
            min_kernel_parts = (
                [int(x) for x in match.group(1).split(".")] if match else [5, 0]
            )
        if min_kernel_parts == [0, 0]:
            min_kernel_parts = [5, 0]

        try:
            resp = requests.get(self.ubuntu_mainline_base, timeout=15)
            if resp.status_code != 200:
                return ubuntu_kernels

            seen = set()
            for href, ver in re.findall(
                r'href="(v(\d+\.\d+(?:\.\d+)?(?:-rc\d+)?)/)"', resp.text
            ):
                if ver in seen:
                    continue
                seen.add(ver)

                parts = ver.replace("-rc", ".").split(".")
                if len(parts) < 2:
                    continue
                try:
                    s_parts = [int(parts[0]), int(parts[1])]
                except ValueError:
                    continue

                if not (
                    s_parts[0] > min_kernel_parts[0]
                    or (
                        s_parts[0] == min_kernel_parts[0]
                        and s_parts[1] >= min_kernel_parts[1]
                    )
                ):
                    continue

                meta = metadata.get(ver, {})
                default_moniker = "rc" if "-rc" in ver else "stable"
                ubuntu_kernels.append({
                    "version": ver,
                    "moniker": meta.get("moniker", default_moniker),
                    "iseol": meta.get("iseol", False),
                    "page_url": urljoin(self.ubuntu_mainline_base, href),
                    "kernel_type": "ubuntu_mainline",
                })

            ubuntu_kernels.sort(
                key=lambda k: self._version_sort_key(k["version"]), reverse=True
            )
        except Exception as e:
            print(f"Error fetching Ubuntu mainline kernels: {e}")

        return ubuntu_kernels

    def resolve_ubuntu_mainline_debs(self, page_url, version=None, arch=None, flavor="generic"):
        """Resolve .deb download URLs for an Ubuntu mainline kernel release."""
        arch = arch or self._detect_debian_arch()
        if not page_url.endswith("/"):
            page_url += "/"

        resp = requests.get(page_url, timeout=15)
        resp.raise_for_status()
        page_html = resp.text

        raw_links = re.findall(r'href="([^"]+\.deb)"', page_html)
        arch_links = []
        all_headers_url = None

        for href in raw_links:
            if "dbgsym" in href or href.endswith(".ddeb"):
                continue
            full_url = urljoin(page_url, href)
            fname = os.path.basename(href)

            # Collect _all headers (often hosted under amd64/ even for arm64/other arches)
            if fname.startswith("linux-headers-") and fname.endswith("_all.deb"):
                if href.startswith(f"{arch}/") or all_headers_url is None:
                    all_headers_url = full_url
                continue

            is_for_arch = (
                href.startswith(f"{arch}/")
                or ("/" not in href and fname.endswith(f"_{arch}.deb"))
            )
            if is_for_arch and fname.endswith(f"_{arch}.deb"):
                arch_links.append((fname, full_url))

        # Fallback: inspect {page_url}{arch}/ directly if HEADER.html omitted links
        if not arch_links:
            arch_dir_url = urljoin(page_url, f"{arch}/")
            try:
                arch_resp = requests.get(arch_dir_url, timeout=15)
                if arch_resp.status_code == 200:
                    for href in re.findall(r'href="([^"]+\.deb)"', arch_resp.text):
                        if "dbgsym" in href or href.endswith(".ddeb"):
                            continue
                        full_url = urljoin(arch_dir_url, href)
                        fname = os.path.basename(href)
                        if fname.startswith("linux-headers-") and fname.endswith("_all.deb"):
                            all_headers_url = full_url
                        elif fname.endswith(f"_{arch}.deb"):
                            arch_links.append((fname, full_url))
            except Exception:
                pass

        # If non-amd64 arch still lacks _all headers, check amd64/ directory
        if all_headers_url is None and arch != "amd64":
            amd64_dir_url = urljoin(page_url, "amd64/")
            try:
                amd64_resp = requests.get(amd64_dir_url, timeout=10)
                if amd64_resp.status_code == 200:
                    for href in re.findall(r'href="([^"]+\.deb)"', amd64_resp.text):
                        fname = os.path.basename(href)
                        if fname.startswith("linux-headers-") and fname.endswith("_all.deb"):
                            all_headers_url = urljoin(amd64_dir_url, href)
                            break
            except Exception:
                pass

        flavor_token = f"-{flavor}_"
        signed_image = None
        unsigned_image = None
        modules_urls = []
        arch_headers_url = None
        seen_urls = set()

        for fname, full_url in arch_links:
            if full_url in seen_urls or flavor_token not in fname:
                continue
            seen_urls.add(full_url)
            if fname.startswith("linux-image-unsigned-"):
                unsigned_image = full_url
            elif fname.startswith("linux-image-"):
                signed_image = full_url
            elif fname.startswith("linux-modules-"):
                modules_urls.append(full_url)
            elif fname.startswith("linux-headers-"):
                arch_headers_url = full_url

        image_url = signed_image or unsigned_image
        if not image_url:
            ver_label = version or page_url.rstrip("/").split("/")[-1]
            if f"Test {arch}/build failed" in page_html:
                raise RuntimeError(
                    f"Ubuntu Mainline build for {ver_label} ({arch}) failed on "
                    "kernel.ubuntu.com; no .deb packages are available for this architecture."
                )
            raise RuntimeError(
                f"No prebuilt Ubuntu Mainline '{flavor}' kernel image found for "
                f"{ver_label} ({arch}) at {page_url}."
            )

        deb_urls = []
        if all_headers_url:
            deb_urls.append(all_headers_url)
        if arch_headers_url:
            deb_urls.append(arch_headers_url)
        deb_urls.extend(modules_urls)
        deb_urls.append(image_url)
        return deb_urls

    def _fetch_ubuntu_checksums(self, deb_urls):
        """Fetch SHA-256 checksums from Ubuntu mainline CHECKSUMS files."""
        checksums = {}
        parent_dirs = list(dict.fromkeys(
            url.rsplit("/", 1)[0] + "/" for url in deb_urls if "/" in url
        ))
        for dir_url in parent_dirs:
            try:
                resp = requests.get(urljoin(dir_url, "CHECKSUMS"), timeout=10)
                if resp.status_code != 200:
                    continue
                in_sha256 = False
                for line in resp.text.splitlines():
                    stripped = line.strip()
                    if stripped.lower().startswith("# checksums-sha256"):
                        in_sha256 = True
                        continue
                    if stripped.startswith("#"):
                        if in_sha256 and "checksums-" in stripped.lower():
                            in_sha256 = False
                        continue
                    match = re.match(r"^([0-9a-fA-F]{64})\s+(\S+)$", stripped)
                    if match:
                        digest, fname = match.group(1).lower(), os.path.basename(match.group(2))
                        checksums[fname] = digest
            except Exception as e:
                print(f"Warning: could not fetch CHECKSUMS from {dir_url}: {e}")
        return checksums

    @staticmethod
    def _verify_file_sha256(filepath, expected_hex):
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest().lower() == expected_hex.lower()

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
                versions.sort(
                    key=lambda v_info: self._version_sort_key(v_info["version"]),
                    reverse=True,
                )
                filtered_kernels[series] = versions

        # Add Linux-Zen category
        zen_list = self.fetch_zen_kernels()
        if zen_list:
            filtered_kernels["Linux-Zen"] = zen_list

        # Add Prebuilt DEB category (prebuiltkernels.com)
        prebuilt_list = self.fetch_prebuilt_kernels()
        if prebuilt_list:
            filtered_kernels["Prebuilt DEB (prebuiltkernels.com)"] = prebuilt_list

        # Add Ubuntu Mainline DEB category (kernel.ubuntu.com/mainline/)
        ubuntu_mainline_list = self.fetch_ubuntu_mainline_kernels(
            metadata=metadata, min_kernel_parts=min_kernel_parts
        )
        if ubuntu_mainline_list:
            filtered_kernels["Ubuntu Mainline DEB (kernel.ubuntu.com)"] = (
                ubuntu_mainline_list
            )

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

    def install_ubuntu_mainline_kernel(self, version, page_url, flavor="generic"):
        if os.geteuid() != 0:
            raise PermissionError("Root privileges required to install kernel packages.")

        arch = self._detect_debian_arch()
        print(f"Resolving Ubuntu Mainline .deb packages for Linux {version} ({arch}, {flavor})...")
        deb_urls = self.resolve_ubuntu_mainline_debs(
            page_url, version=version, arch=arch, flavor=flavor
        )
        print(f"Found {len(deb_urls)} package(s) to download:")
        for u in deb_urls:
            print(f"  - {os.path.basename(u)}")

        checksums = self._fetch_ubuntu_checksums(deb_urls)
        return self.install_prebuilt_kernel(version, deb_urls, checksums=checksums)

    def install_prebuilt_kernel(self, version, deb_urls, checksums=None):
        if os.geteuid() != 0:
            raise PermissionError("Root privileges required to install kernel packages.")

        ok, free_mb = self.check_boot_space()
        if not ok:
            print(
                f"WARNING: /boot only has {free_mb} MB free. "
                "At least 350 MB is recommended. Proceeding anyway..."
            )

        print(f"Downloading prebuilt kernel package(s) for version {version}...")
        download_tmp = tempfile.mkdtemp(prefix="prebuilt_kernel_")
        os.chmod(download_tmp, 0o755)
        downloaded_debs = []
        before_kernels = set(self.get_installed_kernels())
        try:
            for url in deb_urls:
                fname = os.path.basename(url)
                dest = os.path.join(download_tmp, fname)
                print(f"Downloading {url}...")
                subprocess.run(["wget", "-q", "--show-progress", "-O", dest, url], check=True)
                if checksums and fname in checksums:
                    print(f"Verifying SHA-256 checksum for {fname}...")
                    if not self._verify_file_sha256(dest, checksums[fname]):
                        raise RuntimeError(
                            f"SHA-256 checksum verification failed for {fname}!"
                        )
                    print(f"SHA-256 verified: {fname}")
                downloaded_debs.append(dest)

            if downloaded_debs:
                print("Installing prebuilt DEB kernel package(s) via APT/dpkg...")
                try:
                    subprocess.run(["apt-get", "install", "-y"] + downloaded_debs, check=True)
                except subprocess.CalledProcessError:
                    core_debs = [
                        d for d in downloaded_debs
                        if not os.path.basename(d).startswith("linux-headers-")
                    ]
                    header_debs = [
                        d for d in downloaded_debs
                        if os.path.basename(d).startswith("linux-headers-")
                    ]
                    installed_core = False
                    if header_debs and core_debs:
                        print(
                            "Full package installation (including headers) failed — "
                            "possibly due to libc6/libssl version mismatch with Ubuntu headers. "
                            "Retrying with kernel image and modules only..."
                        )
                        try:
                            subprocess.run(
                                ["apt-get", "install", "-y"] + core_debs, check=True
                            )
                            installed_core = True
                        except subprocess.CalledProcessError:
                            pass

                    if not installed_core:
                        print("apt-get install failed, falling back to dpkg -i + apt-get install -f...")
                        subprocess.run(["dpkg", "-i"] + downloaded_debs, check=False)
                        subprocess.run(["apt-get", "install", "-f", "-y"], check=True)

                after_kernels = set(self.get_installed_kernels())
                new_kernels = sorted(after_kernels - before_kernels)
                if new_kernels:
                    for k_rel in new_kernels:
                        self.run_dkms(k_rel)
                else:
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
        page_url = None
        if isinstance(version, dict):
            source_url = version.get("source")
            pgp_url = version.get("pgp")
            kernel_type = version.get("kernel_type", "mainline")
            deb_urls = version.get("deb_urls", [])
            page_url = version.get("page_url")
            version = version.get("version")

        if kernel_type == "ubuntu_mainline" or (page_url and not deb_urls and not source_url):
            return self.install_ubuntu_mainline_kernel(version, page_url)

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
        installed_pkgs = []
        try:
            for pattern in [
                f"linux-image-*{version_string}*",
                f"linux-modules-*{version_string}*",
                f"linux-headers-*{version_string}*",
            ]:
                res = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Package}\n", pattern],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                installed_pkgs.extend(
                    [p.strip() for p in res.stdout.splitlines() if p.strip()]
                )

            # Also purge Ubuntu mainline shared `_all` headers package (e.g.
            # linux-headers-7.3.5-070305) if no other flavor still needs it.
            flavor_match = re.match(
                r"^(.+)-(?:generic-64k|generic|lowlatency|lpae)$", version_string
            )
            if flavor_match:
                base_ver = flavor_match.group(1)
                base_hdr = f"linux-headers-{base_ver}"
                res_base = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Package}\n", f"{base_hdr}*"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                base_matches = [
                    p.strip() for p in res_base.stdout.splitlines() if p.strip()
                ]
                other_flavors = [
                    p for p in base_matches
                    if p != base_hdr and p not in installed_pkgs
                ]
                if base_hdr in base_matches and not other_flavors:
                    installed_pkgs.append(base_hdr)

            installed_pkgs = list(dict.fromkeys(installed_pkgs))
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
