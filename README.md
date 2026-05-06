<p>
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/puls-k_icon.svg" width="256" height="256" alt="PULS Kernel Manager Icon"/>
</p>

# PULS Kernel/GRUB Manager

_"2 Days ago, when i was trying to use Debian 12 on a modern Acer system, i find out that kernel comes with it doesn't has Acer fan controller patch inside, installing kernel from bookworm-backports stopped me at 6.12.xx so why we shouldn't go further..."_ That was the main idea while creating this.

PULS Kernel/GRUB Manager is a specialized tool for Linux users who need fine-grained control over their system's heart and boot process. It simplifies the process of fetching, compiling, and installing mainline kernels while ensuring system safety through snapshots and Secure Boot management. Its still in heavy development so expect bugs.

![PULS Kernel Manager Screenshot](https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/screenshot1.png)

## Features

### Kernel Management
- **Mainline Fetching**: Automatically fetch the latest stable and RC kernels directly from kernel.org.
- **Tailored Compilation**: Uses `localmodconfig` to create a lean, high-performance kernel tailored specifically to your hardware.
- **Automatic DKMS**: Rebuilds kernel modules (like NVIDIA drivers) automatically for new kernels.
- **Dependency Automation**: Automatically installs all required build tools before compilation.

### Boot & GRUB Control
- **Parameter Tuning**: Easily modify kernel parameters and GRUB settings.
- **Boot Order**: Visualized boot entry management to set default kernels and manage submenus.
- **Safety Backups**: Automatic timestamped backups of your GRUB configuration before any changes are applied.

### Safety & Security
- **System Snapshots**: Integrated Timeshift support to create system restores before installing new kernels.
- **Secure Boot (MOK)**: Complete Machine Owner Key management to allow custom kernels to boot on UEFI Secure Boot systems.
- **Panic Analysis**: Tools to extract and analyze kernel panic logs from `pstore` and `kdump`.

## Installation

### Dependencies
Before building or running from source, ensure the following system dependencies are met:

**Build Tools:**
`build-essential`, `flex`, `bison`, `libncurses-dev`, `libssl-dev`, `libelf-dev`, `bc`, `rsync`

**System Utilities:**
`kdump-tools`, `dkms`, `python3-gi`, `python3-adw`

**Optional System Utilities:**
`timeshift`, `btrfs-progs`

### Install Debian Package (.deb)
The recommended way for Debian/Ubuntu based systems:
1. Download the latest `.deb` from [Releases](https://github.com/word-sys/puls-kernel-mgr/releases).
2. Install via terminal:
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

## Usage
Launch the application via your application menu or terminal:

**Command Line Interface:**
```bash
puls-kernel-mgr
```

**Graphical User Interface (GTK/Libadwaita):**
```bash
puls-kernel-mgr-gtk
```

---
**Developer:** Barın Güzeldemirci  
**License:** GPL-3.0
