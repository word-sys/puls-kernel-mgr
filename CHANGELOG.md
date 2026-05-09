# Changelog

All notable changes to this project will be documented in this file.

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
