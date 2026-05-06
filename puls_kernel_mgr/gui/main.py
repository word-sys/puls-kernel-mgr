import sys
import os
import threading
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
from fospx_kernel_mgr.core.kernel import KernelManager
from fospx_kernel_mgr.core.grub import GrubManager
from fospx_kernel_mgr.core.safety import SafetyManager
from fospx_kernel_mgr.core.security import SecurityManager


class LiveLogDialog(Adw.Window):
    def __init__(self, title: str, parent):
        super().__init__()
        self.set_title(title)
        self.set_default_size(720, 480)
        self.set_modal(True)
        self.set_transient_for(parent)
        # Adw.ToolbarView requires ≥1.4
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
            self._status_label.set_label(f"✔ {summary}")
            self._status_label.remove_css_class("error")
        else:
            self._status_label.set_label(f"✘ {summary}")
            self._status_label.add_css_class("error")
        self._close_btn.set_sensitive(True)
        self._close_btn.add_css_class("suggested-action" if success else "destructive-action")


class KernelManagerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("FOSPX Kernel/GRUB Manager")
        self.set_default_size(1000, 750)
        
        style_mgr = Adw.StyleManager.get_default()
        style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
        self.kernel_manager = KernelManager()
        self.grub_manager = GrubManager()
        self.safety_manager = SafetyManager()
        self.security_manager = SecurityManager()
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)
        self.view_stack = Adw.ViewStack()
        self.view_stack.set_vexpand(True)
        self.header = Adw.HeaderBar()
        self.switcher = Adw.ViewSwitcher()
        self.switcher.set_stack(self.view_stack)
        self.switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.header.set_title_widget(self.switcher)
        self.main_box.append(self.header)
        self.main_box.append(self.view_stack)
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
        dialog = Gtk.AboutDialog(
            transient_for=self,
            program_name="FOSPX Kernel/GRUB Manager",
            version="0.1.1",
            license_type=Gtk.License.GPL_3_0_ONLY,
            comments="A bootloader and custom kernel management tool\nCreated for advanced OS control.",
            authors=["Barın Güzeldemirci [FOSPX]"]
        )
        dialog.present()



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
        
        clamp_kernels = Adw.Clamp(maximum_size=700)
        clamp_kernels.set_child(self.kernels_group)
        scroll.set_child(clamp_kernels)
        left_box.append(scroll)
        
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_box.set_hexpand(True)
        
        title2 = Gtk.Label(label="Locally Installed Kernels")
        title2.add_css_class("title-2")
        title2.set_halign(Gtk.Align.START)
        right_box.append(title2)
        
        self.installed_kernels_group = Adw.PreferencesGroup()
        installed = self.kernel_manager.get_installed_kernels()
        if not installed:
            self.installed_kernels_group.add(Adw.ActionRow(title="No local kernels found."))
        else:
            for k in installed:
                row = Adw.ActionRow(title=f"Linux {k}")
                row.set_icon_name("drive-harddisk-system-symbolic")
                self.installed_kernels_group.add(row)
                
        scroll_installed = Gtk.ScrolledWindow()
        scroll_installed.set_vexpand(True)
        clamp_installed = Adw.Clamp(maximum_size=700)
        clamp_installed.set_child(self.installed_kernels_group)
        scroll_installed.set_child(clamp_installed)
        right_box.append(scroll_installed)
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
        config_box.append(restore_btn)
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
        
        dep_group = Adw.PreferencesGroup()
        self.dep_row = Adw.ActionRow(title="Install Required Tools")
        self.dep_row.set_subtitle(
            "Installs snapshot tools (timeshift, btrfs-progs, kdump-tools) "
            "and kernel build prerequisites (build-essential, flex, bison, "
            "libncurses-dev, libssl-dev, libelf-dev, bc, rsync)"
        )
        dep_btn = Gtk.Button(label="Install Now")
        dep_btn.set_valign(Gtk.Align.CENTER)
        dep_btn.add_css_class("suggested-action")
        dep_btn.connect("clicked", self.on_install_deps)
        self.dep_row.add_suffix(dep_btn)
        dep_group.add(self.dep_row)
        
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


    def on_install_deps(self, btn):
        btn.set_sensitive(False)
        btn.set_label("Installing...")
        def _reenable():
            GLib.idle_add(btn.set_sensitive, True)
            GLib.idle_add(btn.set_label, "Install Now")
        self._run_privileged_action(
            "from fospx_kernel_mgr.core.safety import SafetyManager; SafetyManager().install_dependencies()",
            "Dependencies installed successfully.",
            dialog_title="Installing Dependencies",
            on_done=_reenable,
        )

    def on_create_snapshot(self, btn):
        self._run_privileged_action(
            "from fospx_kernel_mgr.core.safety import SafetyManager; SafetyManager().create_snapshot()",
            "Timeshift snapshot created successfully.",
            dialog_title="Creating Timeshift Snapshot",
        )

    def on_analyze_panics(self, btn):
        logs = self.safety_manager.analyze_panic()
        self.panic_view.get_buffer().set_text(logs)

    def on_generate_mok(self, btn):
        self._run_privileged_action(
            "from fospx_kernel_mgr.core.security import SecurityManager; SecurityManager().generate_mok()",
            "MOK Generated in /var/lib/shim-signed/mok",
            dialog_title="Generate Machine Owner Key",
        )

    def on_enroll_mok(self, btn):
        pw = self.mok_pw_entry.get_text()
        if not pw:
            self.show_message("Error", "Please provide an enrollment password.")
            return
        self._run_privileged_action(
            f"from fospx_kernel_mgr.core.security import SecurityManager; SecurityManager().enroll_mok('{pw}')",
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
            f"from fospx_kernel_mgr.core.grub import GrubManager; m=GrubManager(); m.write_advanced_config({cfg_repr})",
            "GRUB configuration saved and updated successfully.",
            dialog_title="Applying GRUB Configuration",
        )

    def on_install_kernel(self, btn, version):
        vdict_repr = repr(version)
        v_str = version.get('version', '')
        self._run_privileged_action(
            f"from fospx_kernel_mgr.core.kernel import KernelManager; KernelManager().compile_and_install({vdict_repr}, use_menuconfig=False)",
            f"Kernel {v_str} compiled and installed successfully! Check Boot Manager to set it as default.",
            dialog_title=f"Compiling & Installing Linux {v_str}",
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
            err = Adw.ActionRow(title=f"Error loading kernels: {e}")
            self.kernels_group.add(err)
        return False

class KernelManagerApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id='com.fospx.kernelmgr', **kwargs)
        
    def do_activate(self):
        self.show_pre_launch_warning()

    def show_pre_launch_warning(self):
        win = Adw.ApplicationWindow(application=self)
        win.set_title("FOSPX Kernel Manager - Security Warning")
        win.set_default_size(450, 250)
        
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
    app = KernelManagerApp()
    app.run(sys.argv)
