# Changelog

All notable changes to this project will be documented in this file.

## [1.3.1] - 2026-11-21

### Added
- **Ubuntu Mainline DEB Kernels**: Added support for browsing, downloading, and installing pre-compiled `.deb` kernel packages directly from Ubuntu's Mainline Kernel PPA (`https://kernel.ubuntu.com/mainline/`) in both the GUI and CLI.
- **Automatic Architecture Detection & Checksum Verification**: Automatically detects the host Debian architecture (`dpkg --print-architecture`), resolves the matching `generic` flavor packages (including shared `_all.deb` headers across architectures), and verifies downloaded `.deb` files against Ubuntu's official `CHECKSUMS` SHA-256 hashes before installation.

### Improved
- **Prebuilt Kernel Installation & DKMS**: Added `/boot` free-space checks, graceful fallback to kernel image + modules if Ubuntu headers hit library dependency mismatches on Debian/older Ubuntu releases, accurate DKMS targeting for the newly installed kernel release string, and dedicated download/install dialog titles for prebuilt `.deb` packages.
- **Ubuntu Mainline Kernel Removal**: `remove_kernel()` now also purges `linux-modules-*` packages and orphaned shared `_all` `linux-headers-*` packages cleanly via `apt-get purge`.
- **Semantic Kernel Version Sorting**: Properly orders release candidates below final releases (e.g. `7.3.5 > 7.3 > 7.3-rc7`).

## [1.3.0] - 2026-08-09

### Added
- **Package-Managed Builds (`bindeb-pkg`)**: Kernel source builds are now compiled into native `.deb` packages via `bindeb-pkg` and installed through `apt`/`dpkg` to maintain system package database integrity.
- **Linux-Zen Kernel Support**: Added support for fetching, compiling, and packaging Linux-Zen performance kernels.
- **Prebuilt DEB Kernels**: Integrated support for fetching and installing pre-compiled `.deb` kernel packages (such as from `prebuiltkernels.com`).
- **Package Purging**: Kernel uninstallation now uses `apt-get purge` to cleanly remove `.deb` packages and execute package manager hooks.

## [1.2.0] - 2026-07-20

### Added
- **Turkish Language Support**: Added Turkish language support to the application.

## [0.2.0] - 2026-05-09

### Added
- **Dashboard**: Added a new Dashboard page with system overview cards.
- **Kernel Removal**: Implemented kernel removal, including protection against removing the currently running kernel.
- **Menuconfig**: Added a menuconfig toggle in the GUI Kernels page.
- **Boot Once**: Added a "Boot Once" button utilizing `grub-reboot`.
- **GRUB Backup History**: Introduced a GRUB backup history viewer with per-entry restore functionality.
- **Dependency Status**: Added per-package dependency status display (OK/Fail per tool).
- **Pre-launch Warning**: Added a "Don't show again" option on the pre-launch warning dialog.
- **Streaming Download**: Enabled streaming downloads with live progress in the log dialog.
- **GRUB Backup Rotation**: Implemented GRUB backup rotation (keeps the last 10 backups).
- **AppStream**: Added AppStream metainfo for GNOME Software integration.

### Fixed
- **GNOME Taskbar**: Fixed an issue where the GNOME taskbar showed `com.puls.kernelmgr` instead of `PULS Kernel/GRUB Manager`.
- **App Icon**: Resolved an issue where the app icon didn't display correctly for both source runs and `.deb` installs.
- **Security**: Fixed an issue where the MOK enrollment password was injected into shell strings.
- **GRUB Root UUID**: Fixed `generate_custom_entry()` in GRUB to use the real root UUID.
