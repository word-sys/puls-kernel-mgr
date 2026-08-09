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
from puls_kernel_mgr.core.translation import TranslationManager
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
        self.tm = TranslationManager()
        self.tr = lambda key, **kwargs: GLib.markup_escape_text(self.tm.tr(key, **kwargs))

        self.set_title(self.tr("app_title"))
        self.set_default_size(780, 560)
        self.set_size_request(540, 380)

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
        self.brand_label = Gtk.Label(label=self.tr("app_title"))
        self.brand_label.add_css_class("heading")
        brand_box.append(self.brand_label)
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
        self.lang_button = Gtk.Button()
        self.lang_button.set_valign(Gtk.Align.CENTER)
        self.lang_button.add_css_class("flat")
        self.update_lang_button_label()
        self.lang_button.connect("clicked", self.on_lang_toggle_clicked)
        self.header.pack_end(self.lang_button)

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        self.popover = Gtk.PopoverMenu()
        self.menu_model = Gio.Menu()
        self.menu_model.append(self.tr("about"), "app.about")
        self.popover.set_menu_model(self.menu_model)
        menu_button.set_popover(self.popover)
        self.header.pack_end(menu_button)
        app = self.get_application()
        if not app.lookup_action("about"):
            action = Gio.SimpleAction.new("about", None)
            action.connect("activate", self.show_about_dialog)
            app.add_action(action)

    def on_lang_toggle_clicked(self, btn):
        self.tm.toggle_lang()
        self.update_lang_button_label()
        self.update_ui_texts()

    def update_lang_button_label(self):
        target = "TR" if self.tm.get_current_lang() == "en" else "EN"
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image.new_from_icon_name("preferences-desktop-locale-symbolic")
        label = Gtk.Label(label=target)
        box.append(icon)
        box.append(label)
        self.lang_button.set_child(box)

    def show_about_dialog(self, action, param):
        kwargs = dict(
            transient_for=self,
            program_name=self.tr("app_title"),
            version=__version__,
            license_type=Gtk.License.GPL_3_0_ONLY,
            comments=self.tr("about_comments"),
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

    def update_ui_texts(self):
        self.set_title(self.tr("app_title"))
        self.brand_label.set_label(self.tr("app_title"))
        self.dashboard_page_stack.set_title(self.tr("dashboard"))
        self.kernels_page_stack.set_title(self.tr("kernels"))
        self.grub_page_stack.set_title(self.tr("boot_manager"))
        self.safety_security_page_stack.set_title(self.tr("safety_security"))

        self.menu_model.remove_all()
        self.menu_model.append(self.tr("about"), "app.about")

        self.refresh_dashboard()
        self.kernels_installed_label.set_label(self.tr("locally_installed_kernels"))
        self.mainline_label.set_label(self.tr("kernel_type_mainline"))
        self.zen_label.set_label(self.tr("kernel_type_zen"))
        self.prebuilt_label.set_label(self.tr("kernel_type_prebuilt"))
        self.mc_row.set_title(self.tr("advanced_menuconfig"))
        self.mc_row.set_subtitle(self.tr("menuconfig_desc"))
        self._refresh_installed_kernels()
        GLib.idle_add(self.load_kernels)

        self.grub_title.set_label(self.tr("grub_configuration"))
        self.grub_desc.set_label(self.tr("grub_desc"))
        self.grub_settings_group.set_title(self.tr("settings"))
        self.default_entry_row.set_title(self.tr("default_boot_entry"))
        self.timeout_row.set_title(self.tr("grub_timeout"))
        self.cmdline_row.set_title(self.tr("kernel_parameters"))
        self.safe_mode_row.set_title(self.tr("enable_safe_mode"))
        self.theme_row.set_title(self.tr("grub_theme_path"))
        self.grub_save_btn.set_label(self.tr("dry_run_apply"))
        self.grub_restore_btn.set_label(self.tr("restore_backup"))
        self.boot_once_group.set_title(self.tr("one_time_boot"))
        self.boot_once_group.set_description(self.tr("one_time_boot_desc"))
        self.boot_once_row.set_title(self.tr("boot_once_into"))
        self.boot_once_row.set_subtitle(self.tr("grub_reboot_desc"))
        self.boot_once_entry.set_placeholder_text(self.tr("entry_index_placeholder"))
        self.boot_once_btn.set_label(self.tr("set"))
        self.boot_order_title.set_label(self.tr("current_boot_order"))
        self.boot_order_desc.set_label(self.tr("boot_order_desc"))
        self.backups_title.set_label(self.tr("grub_config_backups"))
        self.refresh_grub_order()
        self._refresh_grub_backups()

        self.safety_title.set_label(self.tr("system_safety"))
        self.refresh_dependency_list()
        self.snap_row.set_title(self.tr("create_pre_update_snap"))
        self.snap_row.set_subtitle(self.tr("timeshift_desc"))
        self.snap_btn.set_label(self.tr("create_snapshot_btn"))
        self.sec_title.set_label(self.tr("secure_boot_config"))
        self.sec_group.set_title(self.tr("mok_management"))
        self.sec_group.set_description(self.tr("mok_desc"))
        self.mok_gen_row.set_title(self.tr("mok_gen_title"))
        self.mok_gen_row.set_subtitle(self.tr("mok_gen_desc"))
        self.mok_gen_btn.set_label(self.tr("generate_key"))
        self.mok_enroll_row.set_title(self.tr("mok_enroll_title"))
        self.mok_enroll_row.set_subtitle(self.tr("mok_enroll_desc"))
        self.mok_pw_entry.set_placeholder_text(self.tr("enrollment_password"))
        self.mok_enroll_btn.set_label(self.tr("enroll"))
        self.panic_title.set_label(self.tr("kernel_panic_logs"))
        self.panic_btn.set_label(self.tr("analyze_panics"))

    def setup_dashboard_page(self):
        self.dashboard_outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.dashboard_outer_box.set_margin_top(20)
        self.dashboard_outer_box.set_margin_bottom(20)
        self.dashboard_outer_box.set_margin_start(20)
        self.dashboard_outer_box.set_margin_end(20)

        self.refresh_dashboard()

        clamp = Adw.Clamp(maximum_size=800)
        clamp.set_child(self.dashboard_outer_box)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_child(clamp)
        self.dashboard_page_stack = self.view_stack.add_titled(scroll, "dashboard", self.tr("dashboard"))
        self.dashboard_page_stack.set_icon_name("go-home-symbolic")

    def refresh_dashboard(self):
        while child := self.dashboard_outer_box.get_first_child():
            self.dashboard_outer_box.remove(child)

        import platform
        title = Gtk.Label(label=self.tr("system_overview"))
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        self.dashboard_outer_box.append(title)

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
            lbl_h = Gtk.Label(label=self.tr(heading))
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
        boot_label = self.tr("mb_free", free_mb=free_mb) if free_mb >= 0 else self.tr("unknown")
        boot_css = None if ok else "error"

        cards_box.append(make_card("system-run-symbolic", "running_kernel", running_kernel))
        cards_box.append(make_card("drive-harddisk-system-symbolic", "grub_default", grub_default))
        cards_box.append(make_card("drive-multidisk-symbolic", "boot_free_space", boot_label, boot_css))
        self.dashboard_outer_box.append(cards_box)

        actions_label = Gtk.Label(label=self.tr("quick_actions"))
        actions_label.add_css_class("title-2")
        actions_label.set_halign(Gtk.Align.START)
        self.dashboard_outer_box.append(actions_label)

        actions_desc = Gtk.Label(label=self.tr("quick_actions_desc"))
        actions_desc.add_css_class("dim-label")
        actions_desc.set_wrap(True)
        actions_desc.set_halign(Gtk.Align.START)
        self.dashboard_outer_box.append(actions_desc)

        qa_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        snap_btn = Gtk.Button(label=self.tr("create_snapshot"))
        snap_btn.set_icon_name("document-save-symbolic")
        snap_btn.add_css_class("pill")
        snap_btn.connect("clicked", self.on_create_snapshot)
        refresh_btn = Gtk.Button(label=self.tr("refresh_kernel_list"))
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("pill")
        def do_refresh(b):
            GLib.idle_add(self.load_kernels)
        refresh_btn.connect("clicked", do_refresh)
        qa_box.append(snap_btn)
        qa_box.append(refresh_btn)
        self.dashboard_outer_box.append(qa_box)

    def setup_kernels_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)

        # 1. Locally Installed Kernels
        self.kernels_installed_label = Gtk.Label(label=self.tr("locally_installed_kernels"))
        self.kernels_installed_label.add_css_class("title-2")
        self.kernels_installed_label.set_halign(Gtk.Align.START)
        vbox.append(self.kernels_installed_label)

        self.installed_kernels_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.installed_kernels_group = Adw.PreferencesGroup()
        self.installed_kernels_container.append(self.installed_kernels_group)
        self._refresh_installed_kernels()
        vbox.append(self.installed_kernels_container)

        # 2. Mainline Linux Kernels
        self.mainline_label = Gtk.Label(label=self.tr("kernel_type_mainline"))
        self.mainline_label.add_css_class("title-2")
        self.mainline_label.set_margin_top(8)
        self.mainline_label.set_halign(Gtk.Align.START)
        vbox.append(self.mainline_label)

        self.mainline_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.append(self.mainline_box)

        # 3. Linux-Zen Kernels
        self.zen_label = Gtk.Label(label=self.tr("kernel_type_zen"))
        self.zen_label.add_css_class("title-2")
        self.zen_label.set_margin_top(8)
        self.zen_label.set_halign(Gtk.Align.START)
        vbox.append(self.zen_label)

        self.zen_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.append(self.zen_box)

        # 4. Prebuilt DEB Kernels
        self.prebuilt_label = Gtk.Label(label=self.tr("kernel_type_prebuilt"))
        self.prebuilt_label.add_css_class("title-2")
        self.prebuilt_label.set_margin_top(8)
        self.prebuilt_label.set_halign(Gtk.Align.START)
        vbox.append(self.prebuilt_label)

        self.prebuilt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.append(self.prebuilt_box)

        # 5. Advanced Config (menuconfig)
        self.mc_row = Adw.ActionRow(title=self.tr("advanced_menuconfig"))
        self.mc_row.set_subtitle(self.tr("menuconfig_desc"))
        self._mc_switch = Gtk.Switch()
        self._mc_switch.set_valign(Gtk.Align.CENTER)
        self._mc_switch.connect("notify::active", lambda s, _: setattr(self, '_use_menuconfig', s.get_active()))
        self.mc_row.add_suffix(self._mc_switch)
        mc_group = Adw.PreferencesGroup()
        mc_group.add(self.mc_row)
        vbox.append(mc_group)

        clamp = Adw.Clamp(maximum_size=800)
        clamp.set_child(vbox)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_child(clamp)

        self.kernels_page_stack = self.view_stack.add_titled(scroll, "kernels", self.tr("kernels"))
        self.kernels_page_stack.set_icon_name("system-software-install-symbolic")

    def setup_grub_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)

        config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.grub_title = Gtk.Label(label=self.tr("grub_configuration"))
        self.grub_title.add_css_class("title-2")
        self.grub_title.set_halign(Gtk.Align.START)
        config_box.append(self.grub_title)
        self.grub_desc = Gtk.Label(label=self.tr("grub_desc"))
        self.grub_desc.set_wrap(True)
        self.grub_desc.set_halign(Gtk.Align.START)
        self.grub_desc.add_css_class("dim-label")
        config_box.append(self.grub_desc)

        self.grub_settings_group = Adw.PreferencesGroup(title=self.tr("settings"))
        config = self.grub_manager.read_default_config()
        current_default = config.get("GRUB_DEFAULT", "0")
        self.default_entry_row = Adw.ActionRow(title=self.tr("default_boot_entry"))
        self.default_entry = Gtk.Entry()
        self.default_entry.set_text(current_default)
        self.default_entry.set_valign(Gtk.Align.CENTER)
        self.default_entry.set_hexpand(True)
        self.default_entry_row.add_suffix(self.default_entry)
        self.grub_settings_group.add(self.default_entry_row)

        self.timeout_row = Adw.ActionRow(title=self.tr("grub_timeout"))
        self.timeout_entry = Gtk.Entry()
        self.timeout_entry.set_text(config.get("GRUB_TIMEOUT", "5"))
        self.timeout_entry.set_valign(Gtk.Align.CENTER)
        self.timeout_row.add_suffix(self.timeout_entry)
        self.grub_settings_group.add(self.timeout_row)

        self.cmdline_row = Adw.ActionRow(title=self.tr("kernel_parameters"))
        self.cmdline_entry = Gtk.Entry()
        self.cmdline_entry.set_text(config.get("GRUB_CMDLINE_LINUX_DEFAULT", "quiet splash"))
        self.cmdline_entry.set_valign(Gtk.Align.CENTER)
        self.cmdline_entry.set_hexpand(True)
        self.cmdline_row.add_suffix(self.cmdline_entry)
        self.grub_settings_group.add(self.cmdline_row)

        self.safe_mode_row = Adw.ActionRow(title=self.tr("enable_safe_mode"))
        self.safe_mode_switch = Gtk.Switch()
        self.safe_mode_switch.set_valign(Gtk.Align.CENTER)
        if "nomodeset" in config.get("GRUB_CMDLINE_LINUX_DEFAULT", ""):
            self.safe_mode_switch.set_active(True)
        self.safe_mode_row.add_suffix(self.safe_mode_switch)
        self.grub_settings_group.add(self.safe_mode_row)

        self.theme_row = Adw.ActionRow(title=self.tr("grub_theme_path"))
        self.theme_entry = Gtk.Entry()
        self.theme_entry.set_text(config.get("GRUB_THEME", ""))
        self.theme_entry.set_valign(Gtk.Align.CENTER)
        self.theme_entry.set_hexpand(True)
        self.theme_row.add_suffix(self.theme_entry)
        self.grub_settings_group.add(self.theme_row)

        self.grub_save_btn = Gtk.Button(label=self.tr("dry_run_apply"))
        self.grub_save_btn.add_css_class("suggested-action")
        self.grub_save_btn.set_halign(Gtk.Align.CENTER)
        self.grub_save_btn.set_margin_top(12)
        self.grub_save_btn.connect("clicked", self.on_save_grub)
        config_box.append(self.grub_settings_group)
        config_box.append(self.grub_save_btn)

        self.boot_once_group = Adw.PreferencesGroup(title=self.tr("one_time_boot"))
        self.boot_once_group.set_description(self.tr("one_time_boot_desc"))
        self.boot_once_row = Adw.ActionRow(title=self.tr("boot_once_into"))
        self.boot_once_row.set_subtitle(self.tr("grub_reboot_desc"))
        self.boot_once_entry = Gtk.Entry()
        self.boot_once_entry.set_placeholder_text(self.tr("entry_index_placeholder"))
        self.boot_once_entry.set_valign(Gtk.Align.CENTER)
        self.boot_once_entry.set_hexpand(True)
        self.boot_once_row.add_suffix(self.boot_once_entry)
        self.boot_once_btn = Gtk.Button(label=self.tr("set"))
        self.boot_once_btn.set_valign(Gtk.Align.CENTER)
        self.boot_once_btn.add_css_class("suggested-action")
        self.boot_once_btn.connect("clicked", self.on_boot_once)
        self.boot_once_row.add_suffix(self.boot_once_btn)
        self.boot_once_group.add(self.boot_once_row)
        config_box.append(self.boot_once_group)

        self.grub_restore_btn = Gtk.Button(label=self.tr("restore_backup"))
        self.grub_restore_btn.add_css_class("destructive-action")
        self.grub_restore_btn.set_halign(Gtk.Align.CENTER)
        self.grub_restore_btn.set_margin_top(12)
        self.grub_restore_btn.connect("clicked", self.on_restore_grub_backup)
        config_box.append(self.grub_restore_btn)

        order_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        order_box.set_margin_top(12)
        self.boot_order_title = Gtk.Label(label=self.tr("current_boot_order"))
        self.boot_order_title.add_css_class("title-2")
        self.boot_order_title.set_halign(Gtk.Align.START)
        order_box.append(self.boot_order_title)

        self.boot_order_desc = Gtk.Label(label=self.tr("boot_order_desc"))
        self.boot_order_desc.set_wrap(True)
        self.boot_order_desc.set_halign(Gtk.Align.START)
        self.boot_order_desc.add_css_class("dim-label")
        order_box.append(self.boot_order_desc)

        self.boot_order_list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        order_box.append(self.boot_order_list_container)
        self.refresh_grub_order()

        self.backups_title = Gtk.Label(label=self.tr("grub_config_backups"))
        self.backups_title.add_css_class("title-2")
        self.backups_title.set_margin_top(12)
        self.backups_title.set_halign(Gtk.Align.START)
        order_box.append(self.backups_title)

        self.backup_group_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.backup_group = Adw.PreferencesGroup()
        self.backup_group_container.append(self.backup_group)
        self._refresh_grub_backups()
        order_box.append(self.backup_group_container)

        vbox.append(config_box)
        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        vbox.append(order_box)

        clamp = Adw.Clamp(maximum_size=800)
        clamp.set_child(vbox)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_child(clamp)

        self.grub_page_stack = self.view_stack.add_titled(scroll, "grub", self.tr("boot_manager"))
        self.grub_page_stack.set_icon_name("drive-harddisk-system-symbolic")

    def refresh_grub_order(self):
        while child := self.boot_order_list_container.get_first_child():
            self.boot_order_list_container.remove(child)

        entries = self.grub_manager.get_grub_entries()
        order_group = Adw.PreferencesGroup()
        if not entries:
            order_group.add(Adw.ActionRow(title=self.tr("no_grub_entries")))
        else:
            for idx, entry in enumerate(entries):
                if entry["type"] == "submenu":
                    expander = Adw.ExpanderRow(title=entry["title"])
                    expander.set_subtitle(self.tr("main_menu_index", idx=idx))
                    for child_idx, child in enumerate(entry["children"]):
                        row = Adw.ActionRow(title=child["title"])
                        full_title = f"{entry['title']}>{child['title']}"
                        row.set_subtitle(self.tr("path_title", full_title=full_title))
                        row.set_icon_name("go-next-symbolic")

                        btn = Gtk.Button(label=self.tr("set_as_default"))
                        btn.set_valign(Gtk.Align.CENTER)
                        btn.add_css_class("suggested-action")
                        btn.connect("clicked", lambda b, t=f"{idx}>{child_idx}": self.default_entry.set_text(t))
                        row.add_suffix(btn)

                        expander.add_row(row)
                    order_group.add(expander)
                else:
                    row = Adw.ActionRow(title=entry["title"])
                    row.set_subtitle(self.tr("main_menu_index", idx=idx))
                    row.set_icon_name("system-run-symbolic")

                    btn = Gtk.Button(label=self.tr("set_as_default"))
                    btn.set_valign(Gtk.Align.CENTER)
                    btn.add_css_class("suggested-action")
                    btn.connect("clicked", lambda b, t=str(idx): self.default_entry.set_text(t))
                    row.add_suffix(btn)

                    order_group.add(row)

        self.boot_order_list_container.append(order_group)

    def setup_safety_security_page(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.safety_title = Gtk.Label(label=self.tr("system_safety"))
        self.safety_title.add_css_class("title-2")
        self.safety_title.set_halign(Gtk.Align.START)
        left_box.append(self.safety_title)

        self.dep_group_clamp = Adw.Clamp(maximum_size=800)
        self.refresh_dependency_list()
        left_box.append(self.dep_group_clamp)

        self.snap_group = Adw.PreferencesGroup()
        self.snap_row = Adw.ActionRow(title=self.tr("create_pre_update_snap"))
        self.snap_row.set_subtitle(self.tr("timeshift_desc"))
        self.snap_btn = Gtk.Button(label=self.tr("create_snapshot_btn"))
        self.snap_btn.set_valign(Gtk.Align.CENTER)
        self.snap_btn.connect("clicked", self.on_create_snapshot)
        self.snap_row.add_suffix(self.snap_btn)
        self.snap_group.add(self.snap_row)
        left_box.append(self.snap_group)

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_margin_top(12)
        self.sec_title = Gtk.Label(label=self.tr("secure_boot_config"))
        self.sec_title.add_css_class("title-2")
        self.sec_title.set_halign(Gtk.Align.START)
        right_box.append(self.sec_title)

        self.sec_group = Adw.PreferencesGroup(title=self.tr("mok_management"))
        self.sec_group.set_description(self.tr("mok_desc"))

        self.mok_gen_row = Adw.ActionRow(title=self.tr("mok_gen_title"))
        self.mok_gen_row.set_subtitle(self.tr("mok_gen_desc"))
        self.mok_gen_btn = Gtk.Button(label=self.tr("generate_key"))
        self.mok_gen_btn.set_valign(Gtk.Align.CENTER)
        self.mok_gen_btn.connect("clicked", self.on_generate_mok)
        self.mok_gen_row.add_suffix(self.mok_gen_btn)
        self.sec_group.add(self.mok_gen_row)

        self.mok_enroll_row = Adw.ActionRow(title=self.tr("mok_enroll_title"))
        self.mok_enroll_row.set_subtitle(self.tr("mok_enroll_desc"))
        self.mok_pw_entry = Gtk.Entry()
        self.mok_pw_entry.set_visibility(False)
        self.mok_pw_entry.set_valign(Gtk.Align.CENTER)
        self.mok_pw_entry.set_placeholder_text(self.tr("enrollment_password"))
        self.mok_enroll_row.add_suffix(self.mok_pw_entry)
        self.mok_enroll_btn = Gtk.Button(label=self.tr("enroll"))
        self.mok_enroll_btn.set_valign(Gtk.Align.CENTER)
        self.mok_enroll_btn.add_css_class("suggested-action")
        self.mok_enroll_btn.connect("clicked", self.on_enroll_mok)
        self.mok_enroll_row.add_suffix(self.mok_enroll_btn)
        self.sec_group.add(self.mok_enroll_row)
        right_box.append(self.sec_group)

        self.panic_title = Gtk.Label(label=self.tr("kernel_panic_logs"))
        self.panic_title.add_css_class("title-2")
        self.panic_title.set_margin_top(16)
        self.panic_title.set_halign(Gtk.Align.START)
        right_box.append(self.panic_title)

        panic_scroll = Gtk.ScrolledWindow()
        panic_scroll.set_min_content_height(100)
        panic_scroll.set_vexpand(True)
        self.panic_view = Gtk.TextView()
        self.panic_view.set_editable(False)
        self.panic_view.set_monospace(True)
        panic_scroll.set_child(self.panic_view)
        self.panic_btn = Gtk.Button(label=self.tr("analyze_panics"))
        self.panic_btn.set_margin_top(8)
        self.panic_btn.connect("clicked", self.on_analyze_panics)
        panic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panic_box.append(panic_scroll)
        panic_box.append(self.panic_btn)
        right_box.append(panic_box)

        vbox.append(left_box)
        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        vbox.append(right_box)

        clamp = Adw.Clamp(maximum_size=800)
        clamp.set_child(vbox)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_child(clamp)

        self.safety_security_page_stack = self.view_stack.add_titled(scroll, "safety_security", self.tr("safety_security"))
        self.safety_security_page_stack.set_icon_name("security-high-symbolic")

    def refresh_dependency_list(self):
        self.dep_group = Adw.PreferencesGroup(title=self.tr("build_system_deps"))
        dep_status = self.safety_manager.get_dependency_status()
        for pkg, installed in dep_status.items():
            row = Adw.ActionRow(title=pkg)
            icon = Gtk.Image.new_from_icon_name(
                "emblem-ok-symbolic" if installed else "dialog-error-symbolic"
            )
            icon.add_css_class("success" if installed else "error")
            row.add_prefix(icon)
            if not installed:
                row.set_subtitle(self.tr("not_installed"))
            self.dep_group.add(row)

        dep_btn_row = Adw.ActionRow(title=self.tr("install_missing_tools"))
        dep_btn_row.set_subtitle(self.tr("install_missing_desc"))
        self.dep_btn = Gtk.Button(label=self.tr("install_now"))
        self.dep_btn.set_valign(Gtk.Align.CENTER)
        self.dep_btn.add_css_class("suggested-action")
        self.dep_btn.connect("clicked", self.on_install_deps)
        dep_btn_row.add_suffix(self.dep_btn)
        self.dep_group.add(dep_btn_row)
        self.dep_group_clamp.set_child(self.dep_group)

    def _run_privileged_action(
        self,
        code_str: str,
        success_msg: str = "Action completed successfully.",
        dialog_title: str = "Running Privileged Action",
        on_done=None,
    ):
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
                    bufsize=1,
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
            self.show_message(self.tr("error"), self.tr("please_enter_entry"))
            return
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.grub import GrubManager; GrubManager().set_kernel_next_boot({title!r})",
            self.tr("next_boot_set", title=title),
            dialog_title=self.tr("setting_one_time_boot"),
        )

    def on_restore_grub_backup(self, btn):
        snapshots = self.grub_manager.backup.list_snapshots()
        if not snapshots:
            self.show_message(self.tr("no_backups"), self.tr("no_grub_backups_found"))
            return
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.grub_backup import GrubBackupManager; m=GrubBackupManager(); m.restore_snapshot({snapshots[0]!r})",
            self.tr("backup_restored_update_grub"),
            dialog_title=self.tr("restoring_grub_backup"),
            on_done=lambda: GLib.idle_add(self._refresh_grub_backups),
        )

    def _refresh_grub_backups(self):
        new_grp = Adw.PreferencesGroup()
        snapshots = self.grub_manager.backup.list_snapshots_with_meta()
        if not snapshots:
            new_grp.add(Adw.ActionRow(title=self.tr("no_backups_yet")))
        else:
            for snap in snapshots:
                row = Adw.ActionRow(title=snap["date"])
                row.set_icon_name("document-open-recent-symbolic")
                restore_btn = Gtk.Button(label=self.tr("restore"))
                restore_btn.set_valign(Gtk.Align.CENTER)
                restore_btn.add_css_class("destructive-action")
                restore_btn.connect("clicked", self._on_restore_specific, snap["name"])
                row.add_suffix(restore_btn)
                new_grp.add(row)

        if hasattr(self, 'backup_group_container'):
            self.backup_group_container.set_child(new_grp)
        self.backup_group = new_grp

    def _on_restore_specific(self, btn, snapshot_name):
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.grub_backup import GrubBackupManager; GrubBackupManager().restore_snapshot({snapshot_name!r})",
            self.tr("backup_restored_success"),
            dialog_title=self.tr("restoring_grub_backup"),
            on_done=lambda: GLib.idle_add(self._refresh_grub_backups),
        )

    def on_install_deps(self, btn):
        btn.set_sensitive(False)
        btn.set_label(self.tr("installing_dots"))
        def _reenable():
            GLib.idle_add(btn.set_sensitive, True)
            GLib.idle_add(btn.set_label, self.tr("install_now"))
        self._run_privileged_action(
            "from puls_kernel_mgr.core.safety import SafetyManager; SafetyManager().install_dependencies()",
            self.tr("dependencies_installed_success"),
            dialog_title=self.tr("installing_dependencies"),
            on_done=_reenable,
        )

    def on_create_snapshot(self, btn):
        self._run_privileged_action(
            "from puls_kernel_mgr.core.safety import SafetyManager; SafetyManager().create_snapshot()",
            self.tr("timeshift_created_success"),
            dialog_title=self.tr("creating_timeshift_snapshot"),
        )

    def on_analyze_panics(self, btn):
        logs = self.safety_manager.analyze_panic()
        self.panic_view.get_buffer().set_text(logs)

    def on_generate_mok(self, btn):
        self._run_privileged_action(
            "from puls_kernel_mgr.core.security import SecurityManager; SecurityManager().generate_mok()",
            self.tr("mok_generated_success"),
            dialog_title=self.tr("generate_mok_title"),
        )

    def on_enroll_mok(self, btn):
        pw = self.mok_pw_entry.get_text()
        if not pw:
            self.show_message(self.tr("error"), self.tr("please_provide_password"))
            return
        import json, tempfile
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
            self.tr("mok_enroll_submitted"),
            dialog_title=self.tr("enroll_mok_title"),
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
            self.tr("grub_config_saved_success"),
            dialog_title=self.tr("applying_grub_config"),
        )

    def on_install_kernel(self, btn, version):
        vdict_repr = repr(version)
        v_str = version.get('version', '')
        use_mc = getattr(self, '_use_menuconfig', False)
        self._run_privileged_action(
            f"from puls_kernel_mgr.core.kernel import KernelManager; KernelManager().compile_and_install({vdict_repr}, use_menuconfig={use_mc})",
            self.tr("kernel_compile_installed_success", v_str=v_str),
            dialog_title=self.tr("compiling_installing_kernel", v_str=v_str),
            on_done=lambda: GLib.idle_add(self._refresh_installed_kernels),
        )

    def load_kernels(self):
        while child := self.mainline_box.get_first_child():
            self.mainline_box.remove(child)
        while child := self.zen_box.get_first_child():
            self.zen_box.remove(child)
        while child := self.prebuilt_box.get_first_child():
            self.prebuilt_box.remove(child)

        loading_grp = Adw.PreferencesGroup()
        spin_row = Adw.ActionRow(title=self.tr("loading_dots"))
        spinner = Gtk.Spinner()
        spinner.start()
        spin_row.add_prefix(spinner)
        loading_grp.add(spin_row)
        self.mainline_box.append(loading_grp)

        def _bg_fetch():
            try:
                kernels = self.kernel_manager.fetch_available_kernels()
            except Exception as exc:
                kernels = exc
            GLib.idle_add(self._apply_loaded_kernels, kernels)

        threading.Thread(target=_bg_fetch, daemon=True).start()
        return False

    def _apply_loaded_kernels(self, kernels):
        while child := self.mainline_box.get_first_child():
            self.mainline_box.remove(child)
        while child := self.zen_box.get_first_child():
            self.zen_box.remove(child)
        while child := self.prebuilt_box.get_first_child():
            self.prebuilt_box.remove(child)

        if isinstance(kernels, Exception):
            err_group = Adw.PreferencesGroup()
            err_group.add(Adw.ActionRow(title=self.tr("error_loading_kernels", e=str(kernels))))
            self.mainline_box.append(err_group)
            return False

        mainline_grp = Adw.PreferencesGroup()
        zen_grp = Adw.PreferencesGroup()
        prebuilt_grp = Adw.PreferencesGroup()

        has_zen = False
        has_prebuilt = False
        has_mainline = False

        for series, versions in kernels.items():
            if "Zen" in series:
                has_zen = True
                for k_info in versions:
                    v_str = k_info.get("version", "Unknown")
                    row = Adw.ActionRow(title=f"Linux-Zen {v_str}")
                    btn = Gtk.Button(label=self.tr("compile_and_install"))
                    btn.set_valign(Gtk.Align.CENTER)
                    btn.add_css_class("suggested-action")
                    btn.connect("clicked", self.on_install_kernel, k_info)
                    row.add_suffix(btn)
                    zen_grp.add(row)
            elif "Prebuilt" in series:
                pass
            else:
                has_mainline = True
                expander = Adw.ExpanderRow(title=f"Series {series}")
                for k_info in versions:
                    v_str = k_info.get("version", "Unknown")
                    moniker = k_info.get("moniker", "")
                    iseol = k_info.get("iseol", False)
                    title = f"{v_str} [{moniker.upper()}]"
                    if iseol:
                        title += " (EOL)"
                    row = Adw.ActionRow(title=title)
                    btn = Gtk.Button(label=self.tr("compile_and_install"))
                    btn.set_valign(Gtk.Align.CENTER)
                    btn.add_css_class("suggested-action")
                    btn.connect("clicked", self.on_install_kernel, k_info)
                    row.add_suffix(btn)
                    expander.add_row(row)
                mainline_grp.add(expander)

        # Group prebuilt kernels by moniker into expander rows
        prebuilt_items = kernels.get("Prebuilt DEB (prebuiltkernels.com)", [])
        prebuilt_by_moniker = {}
        for k_info in prebuilt_items:
            mon = k_info.get("moniker", "prebuilt").capitalize()
            if mon not in prebuilt_by_moniker:
                prebuilt_by_moniker[mon] = []
            if len(prebuilt_by_moniker[mon]) < 10:
                prebuilt_by_moniker[mon].append(k_info)

        for mon, p_list in prebuilt_by_moniker.items():
            has_prebuilt = True
            p_expander = Adw.ExpanderRow(title=f"Prebuilt {mon} ({len(p_list)} builds)")
            for k_info in p_list:
                v_str = k_info.get("version", "Unknown")
                iseol = k_info.get("iseol", False)
                title = f"Linux {v_str}"
                if iseol:
                    title += " (EOL)"
                row = Adw.ActionRow(title=title)
                btn = Gtk.Button(label="Install DEB")
                btn.set_valign(Gtk.Align.CENTER)
                btn.add_css_class("suggested-action")
                btn.connect("clicked", self.on_install_kernel, k_info)
                row.add_suffix(btn)
                p_expander.add_row(row)
            prebuilt_grp.add(p_expander)

        if has_mainline:
            self.mainline_box.append(mainline_grp)
        if has_zen:
            self.zen_box.append(zen_grp)
        if has_prebuilt:
            self.prebuilt_box.append(prebuilt_grp)

        return False

    def _refresh_installed_kernels(self):
        new_grp = Adw.PreferencesGroup()
        running = os.uname().release
        installed = self.kernel_manager.get_installed_kernels()
        if not installed:
            new_grp.add(Adw.ActionRow(title=self.tr("no_local_kernels")))
        else:
            for k in installed:
                is_running = (k == running)
                row = Adw.ActionRow(title=f"Linux {k}")
                row.set_icon_name("drive-harddisk-system-symbolic")
                if is_running:
                    row.set_subtitle(self.tr("currently_running"))
                    chip = Gtk.Label(label=self.tr("active"))
                    chip.add_css_class("success")
                    row.add_suffix(chip)
                else:
                    rm_btn = Gtk.Button(label=self.tr("remove"))
                    rm_btn.set_valign(Gtk.Align.CENTER)
                    rm_btn.add_css_class("destructive-action")
                    rm_btn.connect("clicked", self.on_remove_kernel, k)
                    row.add_suffix(rm_btn)
                new_grp.add(row)

        if hasattr(self, 'installed_kernels_container'):
            self.installed_kernels_container.set_child(new_grp)
        self.installed_kernels_group = new_grp

    def on_remove_kernel(self, btn, version):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=self.tr("remove_kernel_title", version=version),
            body=self.tr("remove_kernel_body"),
        )
        dialog.add_response("cancel", self.tr("cancel"))
        dialog.add_response("remove", self.tr("remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        def on_response(d, response):
            if response == "remove":
                self._run_privileged_action(
                    f"from puls_kernel_mgr.core.kernel import KernelManager; KernelManager().remove_kernel({version!r})",
                    self.tr("kernel_removed_success", version=version),
                    dialog_title=self.tr("removing_linux_title", version=version),
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
        from puls_kernel_mgr.core.translation import TranslationManager
        tm = TranslationManager()
        tr = tm.tr

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
        win.set_title(tr("app_title"))
        win.set_default_size(480, 340)

        status = Adw.StatusPage()
        status.set_icon_name("dialog-warning-symbolic")
        status.set_title(tr("system_safety_warning"))
        status.set_description(tr("warning_desc1"))

        skip_check = Gtk.CheckButton(label=tr("dont_show_again"))
        skip_check.set_halign(Gtk.Align.CENTER)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_cancel = Gtk.Button(label=tr("cancel"))
        btn_cancel.connect("clicked", lambda b: self.quit())
        btn_continue = Gtk.Button(label=tr("understand_continue"))
        btn_continue.add_css_class("suggested-action")

        def on_continue(b):
            if skip_check.get_active():
                try:
                    prefs_file.parent.mkdir(parents=True, exist_ok=True)
                    prefs = {}
                    if prefs_file.exists():
                        try:
                            prefs = json.loads(prefs_file.read_text())
                        except Exception:
                            pass
                    prefs["skip_warning"] = True
                    prefs_file.write_text(json.dumps(prefs))
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


def main():
    GLib.set_application_name("PULS Kernel/GRUB Manager")
    GLib.set_prgname("puls-kernel-mgr")
    app = KernelManagerApp()
    app.run(sys.argv)
