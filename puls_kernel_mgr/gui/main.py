import sys
import os
import threading
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk
from puls_kernel_mgr.core.kernel import KernelManager
from puls_kernel_mgr.core.grub import GrubManager
from puls_kernel_mgr.core.safety import SafetyManager
from puls_kernel_mgr.core.security import SecurityManager
from puls_kernel_mgr import __version__


def _resolve_icon_path():
    candidates = [
        "/usr/share/icons/hicolor/scalable/apps/puls-k_icon.svg",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "puls-k_icon.svg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "puls-k_icon.svg"),
    ]
    for p in candidates:
        p = os.path.normpath(p)
        if os.path.exists(p):
            return p
    return None


class LiveLogDialog(Adw.Window):
    def __init__(self, title: str, parent):
        super().__init__()
        self.set_title(title)
        self.set_default_size(720, 480)
        self.set_modal(True)
        self.set_transient_for(parent)
        header = Adw.HeaderBar()
        self._status_label = Gtk.Label(label="Running…")
        self._status_label.add_css_class("dim-label")
        self._status_label.set_halign(Gtk.Align.CENTER)
        self._status_label.set_margin_top(8)
        self._status_label.set_margin_bottom(8)
        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_monospace(True)
        self._text_view.set_wrap_mode(Gtk.WrapMode.CHAR)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_margin_start(12)
        scroll.set_margin_end(12)
        scroll.set_child(self._text_view)
        self._close_btn = Gtk.Button(label="Close")
        self._close_btn.set_sensitive(False)
        self._close_btn.set_halign(Gtk.Align.CENTER)
        self._close_btn.set_margin_top(12)
        self._close_btn.set_margin_bottom(16)
        self._close_btn.connect("clicked", lambda _: self.destroy())
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.append(header)
        root.append(self._status_label)
        root.append(scroll)
        root.append(self._close_btn)
        self.set_content(root)

        self._buffer = self._text_view.get_buffer()


    def append_line(self, line: str):
        end_iter = self._buffer.get_end_iter()
        self._buffer.insert(end_iter, line)
        adj = self._text_view.get_parent().get_vadjustment()
        if adj:
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def mark_finished(self, success: bool, summary: str):
        if success:
            self._status_label.set_label(f"OK {summary}")
            self._status_label.remove_css_class("error")
        else:
            self._status_label.set_label(f"FAIL {summary}")
            self._status_label.add_css_class("error")
        self._close_btn.set_sensitive(True)
        self._close_btn.add_css_class("suggested-action" if success else "destructive-action")


class KernelManagerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("PULS Kernel/GRUB Manager")
        self.set_default_size(1060, 780)

        self.icon_path = _resolve_icon_path()

        self.kernel_manager = KernelManager()
        self.grub_manager = GrubManager()
        self.safety_manager = SafetyManager()
        self.security_manager = SecurityManager()
        self._use_menuconfig = False

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)
        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)
        self.header = Adw.HeaderBar()

        brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        brand_box.set_margin_start(10)
        if self.icon_path:
            brand_icon = Gtk.Image.new_from_file(self.icon_path)
            brand_icon.set_pixel_size(32)
            brand_box.append(brand_icon)
        brand_label = Gtk.Label(label="PULS Kernel/GRUB Manager")
        brand_label.add_css_class("heading")
        brand_box.append(brand_label)
        self.header.pack_start(brand_box)

        self.switcher = Adw.ViewSwitcher()
        self.switcher.set_stack(self.view_stack)
        self.switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.header.set_title_widget(self.switcher)
        self.main_box.append(self.header)
        self.main_box.append(self.view_stack)
        self.setup_dashboard_page()
        self.setup_kernels_page()
        self.setup_grub_page()
        self.setup_safety_security_page()
        self.setup_menu()
        GLib.idle_add(self.load_kernels)

    def setup_menu(self):
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        popover = Gtk.PopoverMenu()
        menu_model = Gio.Menu()
        menu_model.append("About", "app.about")
        popover.set_menu_model(menu_model)
        menu_button.set_popover(popover)
        self.header.pack_end(menu_button)
        app = self.get_application()
        if not app.lookup_action("about"):
            action = Gio.SimpleAction.new("about", None)
            action.connect("activate", self.show_about_dialog)
            app.add_action(action)
            
    def show_about_dialog(self, action, param):
        kwargs = dict(
            transient_for=self,
            program_name="PULS Kernel/GRUB Manager",
            version=__version__,
            license_type=Gtk.License.GPL_3_0_ONLY,
            comments="A bootloader and custom kernel management tool.\nCreated for advanced OS control.",
            authors=["Barın Güzeldemirci"],
            website="https://github.com/word-sys/puls-kernel-mgr",
        )
        if self.icon_path:
            try:
                kwargs["logo"] = Gdk.Texture.new_from_filename(self.icon_path)
            except Exception:
                pass
        dialog = Gtk.AboutDialog(**kwargs)
        dialog.present()



    def setup_dashboard_page(self):
        import platform, shutil as _shutil
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_margin_top(28)
        box.set_margin_bottom(28)
        box.set_margin_start(28)
        box.set_margin_end(28)

        title = Gtk.Label(label="System Overview")
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        cards_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        cards_box.set_homogeneous(True)

        def make_card(icon, heading, value, css=None):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.add_css_class("card")
            card.set_margin_top(4)
            card.set_margin_bottom(4)
            p = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            p.set_margin_top(16); p.set_margin_bottom(16)
            p.set_margin_start(16); p.set_margin_end(16)
            ic = Gtk.Image.new_from_icon_name(icon)
            ic.set_pixel_size(32)
            if css:
                ic.add_css_class(css)
            lbl_h = Gtk.Label(label=heading)
            lbl_h.add_css_class("caption")
            lbl_h.add_css_class("dim-label")
            lbl_v = Gtk.Label(label=value)
            lbl_v.add_css_class("title-3")
            lbl_v.set_wrap(True)
            lbl_v.set_xalign(0.5)
            p.append(ic); p.append(lbl_h); p.append(lbl_v)
            card.append(p)
            return card

        running_kernel = platform.release()
        grub_cfg = self.grub_manager.read_default_config()
        grub_default = grub_cfg.get("GRUB_DEFAULT", "0")
        ok, free_mb = self.safety_manager.check_boot_space()
        boot_label = f"{free_mb} MB free" if free_mb >= 0 else "Unknown"
        boot_css = None if ok else "error"

        cards_box.append(make_card("system-run-symbolic", "Running Kernel", running_kernel))
        cards_box.append(make_card("drive-harddisk-system-symbolic", "GRUB Default", grub_default))
        cards_box.append(make_card("drive-multidisk-symbolic", "/boot Free Space", boot_label, boot_css))
        box.append(cards_box)

        actions_label = Gtk.Label(label="Quick Actions")
        actions_label.add_css_class("title-2")
        actions_label.set_halign(Gtk.Align.START)
        box.append(actions_label)

        actions_desc = Gtk.Label(label="Perform common system operations like creating a snapshot or refreshing the list of available kernels.")
        actions_desc.add_css_class("dim-label")
        actions_desc.set_wrap(True)
        actions_desc.set_halign(Gtk.Align.START)
        box.append(actions_desc)

        qa_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        snap_btn = Gtk.Button(label="  Create Snapshot")
        snap_btn.set_icon_name("document-save-symbolic")
        snap_btn.add_css_class("pill")
        snap_btn.connect("clicked", self.on_create_snapshot)
        refresh_btn = Gtk.Button(label="  Refresh Kernel List")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("pill")
        def do_refresh(b):
            if hasattr(self, 'kernels_clamp'):
                self.kernels_group = Adw.PreferencesGroup()
                self.kernels_clamp.set_child(self.kernels_group)
            GLib.idle_add(self.load_kernels)
        refresh_btn.connect("clicked", do_refresh)
        qa_box.append(snap_btn)
        qa_box.append(refresh_btn)
        box.append(qa_box)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(box)
        page = self.view_stack.add_titled(scroll, "dashboard", "Dashboard")
        page.set_icon_name("go-home-symbolic")

    def setup_kernels_page(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        page_box.set_margin_top(24)
        page_box.set_margin_bottom(24)
        page_box.set_margin_start(24)
        page_box.set_margin_end(24)
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        left_box.set_hexpand(True)
        welcome = Gtk.Label(label="Available Upstream Kernels")
        welcome.add_css_class("title-2")
        welcome.set_halign(Gtk.Align.START)
        left_box.append(welcome)
        
        desc = Gtk.Label(label="Select a kernel from kernel.org to download, compile, and install.")
        desc.add_css_class("dim-label")
        desc.set_halign(Gtk.Align.START)
        left_box.append(desc)
        
        self.kernels_group = Adw.PreferencesGroup()
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        
        self.kernels_clamp = Adw.Clamp(maximum_size=700)
        self.kernels_clamp.set_child(self.kernels_group)
        scroll.set_child(self.kernels_clamp)
        left_box.append(scroll)
        
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_hexpand(True)
        
        title2 = Gtk.Label(label="Locally Installed Kernels")
        title2.add_css_class("title-2")
        title2.set_halign(Gtk.Align.START)
        right_box.append(title2)
        
        self.installed_kernels_group = Adw.PreferencesGroup()
        self._refresh_installed_kernels()

        scroll_installed = Gtk.ScrolledWindow()
        scroll_installed.set_vexpand(True)
        self.installed_clamp = Adw.Clamp(maximum_size=700)
        self.installed_clamp.set_child(self.installed_kernels_group)
        scroll_installed.set_child(self.installed_clamp)
        right_box.append(scroll_installed)

        mc_row = Adw.ActionRow(title="Advanced: Use menuconfig")
        mc_row.set_subtitle("Opens kernel configuration editor before compiling")
        self._mc_switch = Gtk.Switch()
        self._mc_switch.set_valign(Gtk.Align.CENTER)
        self._mc_switch.connect("notify::active", lambda s, _: setattr(self, '_use_menuconfig', s.get_active()))
        mc_row.add_suffix(self._mc_switch)
        mc_clamp = Adw.Clamp(maximum_size=700)
        mc_group = Adw.PreferencesGroup()
        mc_group.add(mc_row)
        mc_clamp.set_child(mc_group)
        right_box.append(mc_clamp)
        page_box.append(left_box)
        page_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        page_box.append(right_box)
        GLib.idle_add(self.load_kernels)
        
        page = self.view_stack.add_titled(page_box, "kernels", "Kernels")
        page.set_icon_name("system-software-install-symbolic")

    def setup_grub_page(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        page_box.set_margin_top(24)
        page_box.set_margin_bottom(24)
        page_box.set_margin_start(24)
        page_box.set_margin_end(24)
        config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        config_box.set_hexpand(True)
        title = Gtk.Label(label="GRUB Configuration")
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        config_box.append(title)
        desc = Gtk.Label(label="Edit your primary boot settings below. To set a default boot entry, copy the exact title from the 'Current Boot Order' list on the right. For submenus, use the format 'Submenu Title>Entry Title'.")
        desc.set_wrap(True)
        desc.set_halign(Gtk.Align.START)
        desc.add_css_class("dim-label")
        config_box.append(desc)
        group = Adw.PreferencesGroup(title="Settings")
        config = self.grub_manager.read_default_config()
        current_default = config.get("GRUB_DEFAULT", "0")
        self.default_entry_row = Adw.ActionRow(title="Default Boot Entry Title")
        self.default_entry = Gtk.Entry()
        self.default_entry.set_text(current_default)
        self.default_entry.set_valign(Gtk.Align.CENTER)
        self.default_entry.set_hexpand(True)
        self.default_entry_row.add_suffix(self.default_entry)
        group.add(self.default_entry_row)
        self.timeout_row = Adw.ActionRow(title="GRUB Timeout (seconds)")
        self.timeout_entry = Gtk.Entry()
        self.timeout_entry.set_text(config.get("GRUB_TIMEOUT", "5"))
        self.timeout_entry.set_valign(Gtk.Align.CENTER)
        self.timeout_row.add_suffix(self.timeout_entry)
        group.add(self.timeout_row)
        self.cmdline_row = Adw.ActionRow(title="Kernel Parameters (CMDLINE_DEFAULT)")
        self.cmdline_entry = Gtk.Entry()
        self.cmdline_entry.set_text(config.get("GRUB_CMDLINE_LINUX_DEFAULT", "quiet splash"))
        self.cmdline_entry.set_valign(Gtk.Align.CENTER)
        self.cmdline_entry.set_hexpand(True)
        self.cmdline_row.add_suffix(self.cmdline_entry)
        group.add(self.cmdline_row)
        self.safe_mode_row = Adw.ActionRow(title="Enable Safe Mode (nomodeset)")
        self.safe_mode_switch = Gtk.Switch()
        self.safe_mode_switch.set_valign(Gtk.Align.CENTER)
        if "nomodeset" in config.get("GRUB_CMDLINE_LINUX_DEFAULT", ""):
            self.safe_mode_switch.set_active(True)
        self.safe_mode_row.add_suffix(self.safe_mode_switch)
        group.add(self.safe_mode_row)
        self.theme_row = Adw.ActionRow(title="GRUB Theme Path (.txt file)")
        self.theme_entry = Gtk.Entry()
        self.theme_entry.set_text(config.get("GRUB_THEME", ""))
        self.theme_entry.set_valign(Gtk.Align.CENTER)
        self.theme_entry.set_hexpand(True)
        self.theme_row.add_suffix(self.theme_entry)
        group.add(self.theme_row)
        save_btn = Gtk.Button(label="Dry-Run & Apply Settings")
        save_btn.add_css_class("suggested-action")
        save_btn.set_halign(Gtk.Align.CENTER)
        save_btn.set_margin_top(12)
        save_btn.connect("clicked", self.on_save_grub)
        restore_btn = Gtk.Button(label="Restore Last Working Backup")
        restore_btn.add_css_class("destructive-action")
        restore_btn.set_halign(Gtk.Align.CENTER)
        restore_btn.set_margin_top(12)
        clamp = Adw.Clamp(maximum_size=700)
        clamp.set_child(group)
        config_box.append(clamp)
        config_box.append(save_btn)

        boot_once_group = Adw.PreferencesGroup(title="One-Time Boot")
        boot_once_group.set_description("Boot into a specific entry just once without changing the default.")
        boot_once_row = Adw.ActionRow(title="Boot Once Into Entry")
        boot_once_row.set_subtitle("Uses grub-reboot — takes effect on the next restart only")
        self.boot_once_entry = Gtk.Entry()
        self.boot_once_entry.set_placeholder_text("Entry index or title")
        self.boot_once_entry.set_valign(Gtk.Align.CENTER)
        self.boot_once_entry.set_hexpand(True)
        boot_once_row.add_suffix(self.boot_once_entry)
        boot_once_btn = Gtk.Button(label="Set")
        boot_once_btn.set_valign(Gtk.Align.CENTER)
        boot_once_btn.add_css_class("suggested-action")
        boot_once_btn.connect("clicked", self.on_boot_once)
        boot_once_row.add_suffix(boot_once_btn)
        boot_once_group.add(boot_once_row)
        boot_once_clamp = Adw.Clamp(maximum_size=700)
        boot_once_clamp.set_child(boot_once_group)
        config_box.append(boot_once_clamp)

        restore_btn = Gtk.Button(label="Restore Last Working Backup")
        restore_btn.add_css_class("destructive-action")
        restore_btn.set_halign(Gtk.Align.CENTER)
        restore_btn.set_margin_top(12)
        restore_btn.connect("clicked", self.on_restore_grub_backup)
        order_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        order_box.set_hexpand(True)
        title2 = Gtk.Label(label="Current Boot Order")
        title2.add_css_class("title-2")
        title2.set_halign(Gtk.Align.START)
        order_box.append(title2)
        
        desc2 = Gtk.Label(label="This represents the live menu presented to you when you turn on your computer.")
        desc2.set_wrap(True)
        desc2.set_halign(Gtk.Align.START)
        desc2.add_css_class("dim-label")
        order_box.append(desc2)
        entries = self.grub_manager.get_grub_entries()
        order_group = Adw.PreferencesGroup()
        if not entries:
            order_group.add(Adw.ActionRow(title="No GRUB entries found."))
        else:
            for idx, entry in enumerate(entries):
                if entry["type"] == "submenu":
                    expander = Adw.ExpanderRow(title=entry["title"])
                    expander.set_subtitle(f"Main Menu Index: {idx}")
                    for child_idx, child in enumerate(entry["children"]):
                        row = Adw.ActionRow(title=child["title"])
                        full_title = f"{entry['title']}>{child['title']}"
                        row.set_subtitle(f"Path: {full_title}")
                        row.set_icon_name("go-next-symbolic")
                        
                        btn = Gtk.Button(label="Set as Default")
                        btn.set_valign(Gtk.Align.CENTER)
                        btn.add_css_class("suggested-action")
                        btn.connect("clicked", lambda b, t=f"{idx}>{child_idx}": self.default_entry.set_text(t))
                        row.add_suffix(btn)
                        
                        expander.add_row(row)
                    order_group.add(expander)
                else:
                    row = Adw.ActionRow(title=entry["title"])
                    row.set_subtitle(f"Main Menu Index: {idx}")
                    row.set_icon_name("system-run-symbolic")
                    
                    btn = Gtk.Button(label="Set as Default")
                    btn.set_valign(Gtk.Align.CENTER)
                    btn.add_css_class("suggested-action")
                    btn.connect("clicked", lambda b, t=str(idx): self.default_entry.set_text(t))
                    row.add_suffix(btn)
                    
                    order_group.add(row)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        clamp_order = Adw.Clamp(maximum_size=700)
        clamp_order.set_child(order_group)
        scroll.set_child(clamp_order)
        order_box.append(scroll)

        bk_label = Gtk.Label(label="GRUB Config Backups")
        bk_label.add_css_class("title-2")
        bk_label.set_margin_top(12)
        bk_label.set_halign(Gtk.Align.START)
        order_box.append(bk_label)
        self.backup_group = Adw.PreferencesGroup()
        self._refresh_grub_backups()
        bk_scroll = Gtk.ScrolledWindow()
        bk_scroll.set_min_content_height(140)
        self.bk_clamp = Adw.Clamp(maximum_size=700)
        self.bk_clamp.set_child(self.backup_group)
        bk_scroll.set_child(self.bk_clamp)
        order_box.append(bk_scroll)

        page_box.append(config_box)
        page_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        page_box.append(order_box)
        page = self.view_stack.add_titled(page_box, "grub", "Boot Manager")
        page.set_icon_name("drive-harddisk-system-symbolic")

    def setup_safety_security_page(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        page_box.set_margin_top(24)
        page_box.set_margin_bottom(24)
        page_box.set_margin_start(24)
        page_box.set_margin_end(24)
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        left_box.set_hexpand(True)
        safety_label = Gtk.Label(label="System Safety")
        safety_label.add_css_class("title-2")
        safety_label.set_halign(Gtk.Align.START)
        left_box.append(safety_label)
        
        dep_group = Adw.PreferencesGroup(title="Build &amp; System Dependencies")
        dep_status = self.safety_manager.get_dependency_status()
        for pkg, installed in dep_status.items():
            row = Adw.ActionRow(title=pkg)
            icon = Gtk.Image.new_from_icon_name(
                "emblem-ok-symbolic" if installed else "dialog-error-symbolic"
            )
            icon.add_css_class("success" if installed else "error")
            row.add_prefix(icon)
            if not installed:
                row.set_subtitle("Not installed")
            dep_group.add(row)

        dep_btn_row = Adw.ActionRow(title="Install Missing Tools")
        dep_btn_row.set_subtitle("Installs all missing build and snapshot dependencies via apt")
        dep_btn = Gtk.Button(label="Install Now")
        dep_btn.set_valign(Gtk.Align.CENTER)
        dep_btn.add_css_class("suggested-action")
        dep_btn.connect("clicked", self.on_install_deps)
        dep_btn_row.add_suffix(dep_btn)
        dep_group.add(dep_btn_row)
        
        snap_group = Adw.PreferencesGroup()
        self.snap_row = Adw.ActionRow(title="Create Pre-Update Snapshot")
        self.snap_row.set_subtitle("Uses Timeshift to backup root filesystem")
        snap_btn = Gtk.Button(label="Create Snapshot")
        snap_btn.set_valign(Gtk.Align.CENTER)
        snap_btn.connect("clicked", self.on_create_snapshot)
        self.snap_row.add_suffix(snap_btn)
        snap_group.add(self.snap_row)
        clamp1 = Adw.Clamp(maximum_size=700)
        clamp1.set_child(dep_group)
        clamp2 = Adw.Clamp(maximum_size=700)
        clamp2.set_child(snap_group)
        left_box.append(clamp1)
        left_box.append(clamp2)
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_hexpand(True)
        sec_label = Gtk.Label(label="Secure Boot Configuration")
        sec_label.add_css_class("title-2")
        sec_label.set_halign(Gtk.Align.START)
        right_box.append(sec_label)
        
        sec_group = Adw.PreferencesGroup(title="Machine Owner Key (MOK) Management")
        sec_group.set_description("Required for loading custom kernel modules with UEFI Secure Boot enabled.")
        
        self.mok_gen_row = Adw.ActionRow(title="1. Generate MOK")
        self.mok_gen_row.set_subtitle("Creates a new key pair in /var/lib/shim-signed/mok/")
        gen_btn = Gtk.Button(label="Generate Key")
        gen_btn.set_valign(Gtk.Align.CENTER)
        gen_btn.connect("clicked", self.on_generate_mok)
        self.mok_gen_row.add_suffix(gen_btn)
        sec_group.add(self.mok_gen_row)
        self.mok_enroll_row = Adw.ActionRow(title="2. Enroll MOK")
        self.mok_enroll_row.set_subtitle("Requests key enrollment. Requires reboot.")
        self.mok_pw_entry = Gtk.Entry()
        self.mok_pw_entry.set_visibility(False)
        self.mok_pw_entry.set_valign(Gtk.Align.CENTER)
        self.mok_pw_entry.set_placeholder_text("Enrollment Password")
        self.mok_enroll_row.add_suffix(self.mok_pw_entry)
        enroll_btn = Gtk.Button(label="Enroll")
        enroll_btn.set_valign(Gtk.Align.CENTER)
        enroll_btn.add_css_class("suggested-action")
        enroll_btn.connect("clicked", self.on_enroll_mok)
        self.mok_enroll_row.add_suffix(enroll_btn)
        sec_group.add(self.mok_enroll_row)
        clamp_sec = Adw.Clamp(maximum_size=700)
        clamp_sec.set_child(sec_group)
        right_box.append(clamp_sec)
        panic_label = Gtk.Label(label="Kernel Panic Logs")
        panic_label.add_css_class("title-2")
        panic_label.set_margin_top(16)
        panic_label.set_halign(Gtk.Align.START)
        right_box.append(panic_label)
        panic_scroll = Gtk.ScrolledWindow()
        panic_scroll.set_min_content_height(150)
        panic_scroll.set_vexpand(True)
        self.panic_view = Gtk.TextView()
        self.panic_view.set_editable(False)
        self.panic_view.set_monospace(True)
        panic_scroll.set_child(self.panic_view)
        panic_btn = Gtk.Button(label="Analyze Panics")
        panic_btn.set_margin_top(8)
        panic_btn.connect("clicked", self.on_analyze_panics)
        panic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panic_box.append(panic_scroll)
        panic_box.append(panic_btn)
        clamp3 = Adw.Clamp(maximum_size=700)
        clamp3.set_child(panic_box)
        right_box.append(clamp3)
        
        page_box.append(left_box)
        page_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        page_box.append(right_box)
        
        page = self.view_stack.add_titled(page_box, "safety_security", "Safety & Security")
        page.set_icon_name("security-high-symbolic")

    def _run_privileged_action(
        self,
        code_str: str,
        success_msg: str = "Action completed successfully.",
        dialog_title: str = "Running Privileged Action",
        on_done=None,
    ):
        """Run *code_str* via pkexec and stream all output live into a
        :class:`LiveLogDialog`.  Must be called from the GTK main thread;
        the actual subprocess runs on a daemon thread.

        Args:
            on_done: optional zero-argument callable invoked (from the reader
                     thread) after the subprocess exits, useful for re-enabling
                     buttons or triggering follow-up UI work.
        """

        log_dialog = LiveLogDialog(dialog_title, self)
        log_dialog.present()

        python_path = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        cmd = [
            "pkexec", sys.executable, "-u", "-c",
            f"import sys\nsys.path.insert(0, {python_path!r})\n{code_str}",
        ]

        def _reader():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,          # line-buffered
                )
                for line in proc.stdout:
                    GLib.idle_add(log_dialog.append_line, line)
                proc.wait()
                if proc.returncode == 0:
                    GLib.idle_add(log_dialog.mark_finished, True, success_msg)
                else:
                    GLib.idle_add(
                        log_dialog.mark_finished,
                        False,
                        f"Process exited with code {proc.returncode}.",
                    )
            except Exception as exc:
                GLib.idle_add(log_dialog.mark_finished, False, str(exc))
            finally:
                if callable(on_done):
                    on_done()

        threading.Thread(target=_reader, daemon=True).start()


    def on_boot_once(self, btn):
        title = self.boot_once_entry.get_text().strip()
        if not title:
            self.show_message("Error", "Please enter an entry index or title.")
            return
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.grub import GrubManager; GrubManager().set_kernel_next_boot({title!r})",
            f"Next boot set to: {title}. Reboot to apply.",
            dialog_title="Setting One-Time Boot Entry",
        )

    def on_restore_grub_backup(self, btn):
        snapshots = self.grub_manager.backup.list_snapshots()
        if not snapshots:
            self.show_message("No Backups", "No GRUB backups found.")
            return
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.grub_backup import GrubBackupManager; m=GrubBackupManager(); m.restore_snapshot({snapshots[0]!r})",
            "Backup restored. Run update-grub to apply.",
            dialog_title="Restoring GRUB Backup",
            on_done=lambda: GLib.idle_add(self._refresh_grub_backups),
        )

    def _refresh_grub_backups(self):
        if hasattr(self, 'bk_clamp'):
            self.backup_group = Adw.PreferencesGroup()
            self.bk_clamp.set_child(self.backup_group)
        snapshots = self.grub_manager.backup.list_snapshots_with_meta()
        if not snapshots:
            self.backup_group.add(Adw.ActionRow(title="No backups yet."))
            return
        for snap in snapshots:
            row = Adw.ActionRow(title=snap["date"])
            row.set_icon_name("document-open-recent-symbolic")
            restore_btn = Gtk.Button(label="Restore")
            restore_btn.set_valign(Gtk.Align.CENTER)
            restore_btn.add_css_class("destructive-action")
            restore_btn.connect("clicked", self._on_restore_specific, snap["name"])
            row.add_suffix(restore_btn)
            self.backup_group.add(row)

    def _on_restore_specific(self, btn, snapshot_name):
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.grub_backup import GrubBackupManager; GrubBackupManager().restore_snapshot({snapshot_name!r})",
            "Backup restored successfully.",
            dialog_title="Restoring GRUB Backup",
            on_done=lambda: GLib.idle_add(self._refresh_grub_backups),
        )

    def on_install_deps(self, btn):
        btn.set_sensitive(False)
        btn.set_label("Installing...")
        def _reenable():
            GLib.idle_add(btn.set_sensitive, True)
            GLib.idle_add(btn.set_label, "Install Now")
        self._run_privileged_action(
            "from puls_kernel_mgr.core.safety import SafetyManager; SafetyManager().install_dependencies()",
            "Dependencies installed successfully.",
            dialog_title="Installing Dependencies",
            on_done=_reenable,
        )

    def on_create_snapshot(self, btn):
        self._run_privileged_action(
            "from puls_kernel_mgr.core.safety import SafetyManager; SafetyManager().create_snapshot()",
            "Timeshift snapshot created successfully.",
            dialog_title="Creating Timeshift Snapshot",
        )

    def on_analyze_panics(self, btn):
        logs = self.safety_manager.analyze_panic()
        self.panic_view.get_buffer().set_text(logs)

    def on_generate_mok(self, btn):
        self._run_privileged_action(
            "from puls_kernel_mgr.core.security import SecurityManager; SecurityManager().generate_mok()",
            "MOK Generated in /var/lib/shim-signed/mok",
            dialog_title="Generate Machine Owner Key",
        )

    def on_enroll_mok(self, btn):
        pw = self.mok_pw_entry.get_text()
        if not pw:
            self.show_message("Error", "Please provide an enrollment password.")
            return
        import json, tempfile, pathlib
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump({'password': pw}, tf)
            pw_file = tf.name
        os.chmod(pw_file, 0o600)
        code = (
            f"import json, os\n"
            f"d = json.load(open({pw_file!r})); os.unlink({pw_file!r})\n"
            f"from puls_kernel_mgr.core.security import SecurityManager\n"
            f"SecurityManager().enroll_mok(d['password'])\n"
        )
        self._run_privileged_action(
            code,
            "MOK Enrollment request submitted. Please reboot.",
            dialog_title="Enroll Machine Owner Key",
        )

    def show_message(self, title, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title,
            secondary_text=msg
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()



    def on_save_grub(self, btn):
        config = {
            "GRUB_DEFAULT": self.default_entry.get_text(),
            "GRUB_TIMEOUT": self.timeout_entry.get_text(),
            "GRUB_CMDLINE_LINUX_DEFAULT": self.cmdline_entry.get_text(),
            "GRUB_THEME": self.theme_entry.get_text()
        }
        if self.safe_mode_switch.get_active() and "nomodeset" not in config["GRUB_CMDLINE_LINUX_DEFAULT"]:
            config["GRUB_CMDLINE_LINUX_DEFAULT"] += " nomodeset"
            
        cfg_repr = repr(config)
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.grub import GrubManager; m=GrubManager(); m.write_advanced_config({cfg_repr})",
            "GRUB configuration saved and updated successfully.",
            dialog_title="Applying GRUB Configuration",
        )

    def on_install_kernel(self, btn, version):
        vdict_repr = repr(version)
        v_str = version.get('version', '')
        use_mc = getattr(self, '_use_menuconfig', False)
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.kernel import KernelManager; KernelManager().compile_and_install({vdict_repr}, use_menuconfig={use_mc})",
            f"Kernel {v_str} compiled and installed successfully! Check Boot Manager to set it as default.",
            dialog_title=f"Compiling & Installing Linux {v_str}",
            on_done=lambda: GLib.idle_add(self._refresh_installed_kernels),
        )

    def load_kernels(self):
        try:
            kernels = self.kernel_manager.fetch_available_kernels()
            for series, versions in kernels.items():
                expander = Adw.ExpanderRow(title=f"Series {series}")
                for k_info in versions:
                    v_str = k_info.get("version", "Unknown")
                    moniker = k_info.get("moniker", "")
                    iseol = k_info.get("iseol", False)
                    title = f"{v_str} [{moniker.upper()}]"
                    if iseol:
                        title += " (EOL)"
                    row = Adw.ActionRow(title=title)
                    btn = Gtk.Button(label="Compile & Install")
                    btn.set_valign(Gtk.Align.CENTER)
                    btn.add_css_class("suggested-action")
                    btn.connect("clicked", self.on_install_kernel, k_info)
                    row.add_suffix(btn)
                    expander.add_row(row)
                self.kernels_group.add(expander)
        except Exception as e:
            self.kernels_group.add(Adw.ActionRow(title=f"Error loading kernels: {e}"))
        return False

    def _refresh_installed_kernels(self):
        if hasattr(self, 'installed_clamp'):
            self.installed_kernels_group = Adw.PreferencesGroup()
            self.installed_clamp.set_child(self.installed_kernels_group)
        running = os.uname().release
        installed = self.kernel_manager.get_installed_kernels()
        if not installed:
            self.installed_kernels_group.add(Adw.ActionRow(title="No local kernels found."))
            return
        for k in installed:
            is_running = (k == running)
            row = Adw.ActionRow(title=f"Linux {k}")
            row.set_icon_name("drive-harddisk-system-symbolic")
            if is_running:
                row.set_subtitle("Currently running")
                chip = Gtk.Label(label="active")
                chip.add_css_class("success")
                row.add_suffix(chip)
            else:
                rm_btn = Gtk.Button(label="Remove")
                rm_btn.set_valign(Gtk.Align.CENTER)
                rm_btn.add_css_class("destructive-action")
                rm_btn.connect("clicked", self.on_remove_kernel, k)
                row.add_suffix(rm_btn)
            self.installed_kernels_group.add(row)

    def on_remove_kernel(self, btn, version):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Remove Linux {version}?",
            body="This will permanently delete the kernel, initrd, and modules. This cannot be undone.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        def on_response(d, response):
            if response == "remove":
                self._run_privileged_action(
                    f"from puls_kernel_mgr.core.kernel import KernelManager; KernelManager().remove_kernel({version!r})",
                    f"Kernel {version} removed successfully.",
                    dialog_title=f"Removing Linux {version}",
                    on_done=lambda: GLib.idle_add(self._refresh_installed_kernels),
                )
            d.destroy()
        dialog.connect("response", on_response)
        dialog.present()

class KernelManagerApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id='com.puls.kernelmgr', **kwargs)
        Gtk.Window.set_default_icon_name("puls-k_icon")

    def do_activate(self):
        self.show_pre_launch_warning()

    def show_pre_launch_warning(self):
        import json, pathlib
        prefs_file = pathlib.Path.home() / ".config" / "puls-kernel-mgr" / "prefs.json"
        try:
            prefs = json.loads(prefs_file.read_text())
            if prefs.get("skip_warning"):
                main_win = KernelManagerWindow(application=self)
                main_win.present()
                return
        except Exception:
            pass

        win = Adw.ApplicationWindow(application=self)
        win.set_title("PULS Kernel Manager")
        win.set_default_size(480, 340)

        status = Adw.StatusPage()
        status.set_icon_name("dialog-warning-symbolic")
        status.set_title("System Safety Warning")
        status.set_description(
            "Modifying the Linux kernel is an advanced operation that can "
            "cause system instability or prevent your system from booting.\n\n"
            "Ensure you have backups or snapshots configured before proceeding."
        )

        skip_check = Gtk.CheckButton(label="Don't show this warning again")
        skip_check.set_halign(Gtk.Align.CENTER)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda b: self.quit())
        btn_continue = Gtk.Button(label="I Understand & Continue")
        btn_continue.add_css_class("suggested-action")

        def on_continue(b):
            if skip_check.get_active():
                try:
                    prefs_file.parent.mkdir(parents=True, exist_ok=True)
                    prefs_file.write_text(json.dumps({"skip_warning": True}))
                except Exception:
                    pass
            win.destroy()
            KernelManagerWindow(application=self).present()

        btn_continue.connect("clicked", on_continue)
        btn_box.append(btn_cancel)
        btn_box.append(btn_continue)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(12)
        outer.set_margin_bottom(24)
        outer.set_margin_start(24)
        outer.set_margin_end(24)
        outer.append(status)
        outer.append(skip_check)
        outer.append(btn_box)
        win.set_content(outer)
        win.present()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        win.set_content(box)
        lbl_title = Gtk.Label(label="System Security & Stability Warning")
        lbl_title.add_css_class("title-2")
        box.append(lbl_title)
        lbl_desc = Gtk.Label(label="Modifying the Linux kernel is an advanced operation that can cause system instability, data loss, or prevent your system from booting.\n\nPlease ensure you have backups or snapshots configured before proceeding.")
        lbl_desc.set_wrap(True)
        lbl_desc.set_justify(Gtk.Justification.CENTER)
        box.append(lbl_desc)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda b: self.quit())
        btn_box.append(btn_cancel)
        btn_continue = Gtk.Button(label="I Understand & Continue")
        btn_continue.add_css_class("suggested-action")
        def on_continue_clicked(b):
            win.destroy()
            main_win = KernelManagerWindow(application=self)
            main_win.present()
                
        btn_continue.connect("clicked", on_continue_clicked)
        btn_box.append(btn_continue)
        
        box.append(btn_box)
        win.present()

def main():
    GLib.set_application_name("PULS Kernel/GRUB Manager")
    GLib.set_prgname("puls-kernel-mgr")
    app = KernelManagerApp()
    app.run(sys.argv)
