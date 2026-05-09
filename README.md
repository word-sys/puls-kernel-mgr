<p>
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/puls-k_icon.svg" width="256" height="256" alt="PULS Kernel Manager Icon"/>
</p>

# PULS Kernel/GRUB Manager

> _"2 Days ago, when I was trying to use Debian 12 on a modern Acer system, I found out that the kernel it comes with doesn't have an Acer fan controller patch inside. Installing a kernel from bookworm-backports stopped me at 6.12.xx — so why shouldn't we go further?"_

PULS Kernel/GRUB Manager is a specialized tool for Linux users who need fine-grained control over their system's kernel and boot process. It simplifies fetching, compiling, and installing mainline kernels while ensuring system safety through snapshots and Secure Boot management.

<p align="center">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss0.png" width="49%">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss1.png" width="49%">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss2.png" width="49%">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss3.png" width="49%">
</p>

> **Status:** Heavy development — expect rough edges, bugs and issues, but it works!

---

## Features

### Dashboard
- Live overview of running kernel version
- Current GRUB default entry at a glance
- `/boot` disk free space with low-space warning
- Quick-action buttons: Create Snapshot, Refresh Kernel List

### Kernel Management
- **Mainline Fetching**: Fetch latest stable and RC kernels from kernel.org
- **GPG Verification**: Cryptographic signature check before extraction
- **Tailored Compilation**: `localmodconfig` creates a lean, hardware-specific kernel
- **menuconfig Support**: Optional interactive kernel configuration before compiling
- **Kernel Removal**: Remove installed kernels (blocks removing the running kernel)
- **Automatic DKMS**: Rebuilds modules (e.g. NVIDIA) for new kernels
- **Dependency Automation**: Installs all required build tools before compilation

### Boot & GRUB Control
- **Parameter Tuning**: Modify kernel parameters and GRUB settings
- **Boot Order Viewer**: Visualized boot entry management with set-default buttons
- **Boot Once**: Set a one-time boot entry without changing the default (`grub-reboot`)
- **Safety Backups**: Automatic timestamped backups of GRUB config with dry-run validation
- **Backup History**: View and restore any previous GRUB backup

### Safety & Security
- **System Snapshots**: Integrated Timeshift support with snapshot history
- **Dependency Status**: Per-package OK/Fail display for all required tools
- **Secure Boot (MOK)**: Complete Machine Owner Key management
- **Panic Analysis**: Extract and analyze kernel panic logs from `pstore` and `kdump`

---

## Installation

### Install Debian Package (.deb) — Recommended

```bash
sudo apt update
sudo apt install ./puls-kernel-mgr_*.deb
```

### Build from Source

```bash
git clone https://github.com/word-sys/puls-kernel-mgr.git
cd puls-kernel-mgr
pip install .
```

### Dependencies

**Required:**
```
python3-gi  gir1.2-adw-1  gir1.2-gtk-4.0  pkexec  grub2-common
tar  wget  xz-utils  gpg  openssl  mokutil  dkms  librsvg2-common
```

**Build tools (auto-installed on first run):**
```
build-essential  flex  bison  libncurses-dev  libssl-dev  libelf-dev  bc  rsync
```

**Optional:**
```
timeshift  btrfs-progs  kdump-tools
```

---

## Usage

**Graphical Interface (GTK4/Libadwaita):**
```bash
puls-kernel-mgr-gtk
```

**Command Line Interface:**
```bash
puls-kernel-mgr                            # Interactive TUI
puls-kernel-mgr snapshot create           # Create a Timeshift snapshot
puls-kernel-mgr analyze-panic            # Show kernel panic logs
puls-kernel-mgr generate-mok            # Generate Machine Owner Key
puls-kernel-mgr enroll-mok <password>  # Enroll MOK for Secure Boot
```

---

**Developer:** Barın Güzeldemirci  
**License:** GPL-3.0  
**Homepage:** https://github.com/word-sys/puls-kernel-mgr
