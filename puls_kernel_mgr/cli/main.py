import sys
import os
import curses
from puls_kernel_mgr.core.grub import GrubManager
from puls_kernel_mgr.core.kernel import KernelManager
from puls_kernel_mgr.core.translation import TranslationManager

def interactive_menu(stdscr, title, options, context_dict=None):
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
    current_row = 0
    top_row = 0
    
    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        left_w = max_x // 2
        stdscr.border()
        
        try:
            for y in range(1, max_y - 1):
                stdscr.addch(y, left_w, curses.ACS_VLINE)
            stdscr.addch(0, left_w, curses.ACS_TTEE)
            stdscr.addch(max_y - 1, left_w, curses.ACS_BTEE)
        except curses.error:
            pass
            

        visible_rows = max_y - 4
        if visible_rows < 1:
            visible_rows = 1
            
        if current_row < top_row:
            top_row = current_row
        elif current_row >= top_row + visible_rows:
            top_row = current_row - visible_rows + 1
            
        try:
            stdscr.addstr(1, 2, title[:left_w-4], curses.A_BOLD | curses.color_pair(2))
            
            for idx in range(top_row, min(len(options), top_row + visible_rows)):
                row_str = str(options[idx])[:left_w-6]
                if idx == current_row:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(3 + idx - top_row, 2, f"> {row_str}")
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(3 + idx - top_row, 2, f"  {row_str}")
                    
            if context_dict and current_row in context_dict:
                stdscr.addstr(1, left_w + 2, "Details / Preview", curses.A_BOLD | curses.color_pair(2))
                context_lines = context_dict[current_row].split('\n')
                for i, line in enumerate(context_lines[:max_y-4]):
                    stdscr.addstr(3 + i, left_w + 2, line[:max_x - left_w - 4])
                    
        except curses.error:
            pass #Ignore
            
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(options) - 1:
            current_row += 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            return current_row

def curses_main(stdscr):
    from puls_kernel_mgr.core.grub import GrubManager
    from puls_kernel_mgr.core.kernel import KernelManager
    from puls_kernel_mgr.core.safety import SafetyManager
    from puls_kernel_mgr.core.security import SecurityManager
    import subprocess, os, sys

    while True:
        tm = TranslationManager()
        t = tm.get

        main_options = [
            t("cli_kernels"),
            t("cli_boot_manager"),
            t("cli_safety_security"),
            t("cli_about"),
            t("cli_change_language").format(lang=tm.get_current_lang().upper()),
            t("cli_exit"),
        ]

        g_man = GrubManager()
        cfg = g_man.read_default_config()
        grub_context = t("cli_grub_context_header")
        grub_context += f"\n- {t('cli_grub_default_entry')}: {cfg.get('GRUB_DEFAULT', '0')}"
        grub_context += f"\n- {t('cli_grub_timeout_label')}: {cfg.get('GRUB_TIMEOUT', '5')}s"

        entries = g_man.get_grub_entries()
        grub_context += f"\n\n{t('cli_live_grub_order')}:"
        base_os = entries[0]['title'] if entries else "0"
        for e in entries:
            grub_context += f"\n- {e['title'][:40]}"
            if e.get('type') == 'submenu':
                for child in e.get('children', []):
                    grub_context += f"\n   > {child['title'][:35]}"

        k_man = KernelManager()
        installed = k_man.get_installed_kernels()
        kernels_context = t("cli_kernels_context_header")
        if not installed:
            kernels_context += f"\n- {t('cli_no_custom_kernels')}"
        else:
            for k in installed:
                kernels_context += f"\n- Linux {k}"

        safety_context = t("cli_safety_context")

        context_dict = {
            0: kernels_context,
            1: grub_context,
            2: safety_context,
            3: t("cli_about_context"),
            4: t("cli_change_language_context"),
            5: t("cli_exit_context"),
        }

        choice = interactive_menu(stdscr, t("cli_main_title"), main_options, context_dict)

        if choice == 5:
            break
        elif choice == 4:
            new_lang = "tr" if tm.get_current_lang() == "en" else "en"
            tm.set_lang(new_lang)
        elif choice == 3:
            from puls_kernel_mgr import __version__
            about_context = f"PULS Kernel/GRUB Manager\n{t('cli_version_label')}: {__version__}\n\n{t('cli_developer_label')}: Barin Guzeldemirci\n{t('cli_contact_label')}: baringuzeldemir@gmail.com\n\n{t('cli_license_label')}: GPL-3.0-or-later\n{t('cli_free_software')}"
            interactive_menu(stdscr, t("cli_about_title"), [t("back")], {0: about_context})
        elif choice == 2:
            while True:
                safety_opts = [
                    t("cli_install_deps"),
                    t("cli_create_snapshot"),
                    t("cli_generate_mok"),
                    t("cli_enroll_mok"),
                    t("cli_analyze_panics"),
                    t("back"),
                ]
                s_choice = interactive_menu(stdscr, t("cli_safety_title"), safety_opts)
                if s_choice == 5:
                    break
                elif s_choice == 0:
                    curses.endwin()
                    print(t("cli_installing_deps_progress"))
                    subprocess.run(["sudo", sys.executable, "-c", "from puls_kernel_mgr.core.safety import SafetyManager; SafetyManager().install_dependencies()"])
                    input(t("cli_press_enter"))
                    stdscr.clear()
                elif s_choice == 1:
                    curses.endwin()
                    print(t("cli_creating_snapshot_progress"))
                    subprocess.run(["sudo", sys.executable, "-c", "from puls_kernel_mgr.core.safety import SafetyManager; sm=SafetyManager(); _,msg=sm.create_snapshot(); print(msg)"])
                    input(t("cli_press_enter"))
                    stdscr.clear()
                elif s_choice == 2:
                    curses.endwin()
                    print(t("cli_generating_mok_progress"))
                    subprocess.run(["sudo", sys.executable, "-c", "from puls_kernel_mgr.core.security import SecurityManager; sm=SecurityManager(); _,msg=sm.generate_mok(); print(msg)"])
                    input(t("cli_press_enter"))
                    stdscr.clear()
                elif s_choice == 3:
                    curses.endwin()
                    import getpass, json, tempfile
                    pw = getpass.getpass(t("cli_enter_mok_password"))
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
                        json.dump({'password': pw}, tf)
                        pw_file = tf.name
                    os.chmod(pw_file, 0o600)
                    code = (
                        f"import json, os\n"
                        f"data = json.load(open({pw_file!r}))\n"
                        f"os.unlink({pw_file!r})\n"
                        f"from puls_kernel_mgr.core.security import SecurityManager\n"
                        f"sm = SecurityManager()\n"
                        f"_, msg = sm.enroll_mok(data['password'])\n"
                        f"print(msg)\n"
                    )
                    subprocess.run(["sudo", sys.executable, "-c", code])
                    input(t("cli_press_enter"))
                    stdscr.clear()
                elif s_choice == 4:
                    curses.endwin()
                    print(t("cli_analyzing_panics_progress"))
                    sm = SafetyManager()
                    print(sm.analyze_panic())
                    input(t("cli_press_enter"))
                    stdscr.clear()

        elif choice == 1:
            while True:
                grub_opts = [
                    t("cli_set_default_boot"),
                    t("cli_configure_grub_interactive"),
                    t("cli_restore_factory"),
                    t("back"),
                ]
                g_context_dict = {0: grub_context, 1: grub_context, 2: grub_context, 3: grub_context}
                g_choice = interactive_menu(stdscr, t("cli_boot_manager_title"), grub_opts, g_context_dict)
                if g_choice == 3:
                    break
                elif g_choice == 2:
                    curses.endwin()
                    manager = GrubManager()
                    snaps = manager.backup.list_snapshots()
                    if snaps:
                        manager.backup.restore_snapshot(snaps[-1])
                        print(t("cli_restored_defaults"))
                    else:
                        print(t("no_grub_backups_found"))
                    input()
                    stdscr.clear()
                elif g_choice == 1:
                    stdscr.clear()
                    stdscr.addstr(1, 2, t("cli_enter_grub_timeout"), curses.A_BOLD)
                    stdscr.refresh()
                    curses.echo()
                    timeout_bytes = stdscr.getstr(3, 2)
                    timeout = timeout_bytes.decode('utf-8').strip()
                    if not timeout:
                        curses.noecho()
                        stdscr.clear()
                        continue
                    stdscr.clear()
                    stdscr.addstr(1, 2, t("cli_enter_cmdline"), curses.A_BOLD)
                    stdscr.refresh()
                    cmdline_bytes = stdscr.getstr(3, 2)
                    curses.noecho()
                    cmdline = cmdline_bytes.decode('utf-8').strip()
                    if not cmdline:
                        cmdline = cfg.get("GRUB_CMDLINE_LINUX_DEFAULT", "")
                    curses.endwin()
                    manager = GrubManager()
                    manager.write_advanced_config({"GRUB_TIMEOUT": timeout, "GRUB_CMDLINE_LINUX_DEFAULT": cmdline})
                    print(t("cli_grub_updated"))
                    input()
                    stdscr.clear()
                elif g_choice == 0:
                    stdscr.clear()
                    stdscr.addstr(1, 2, t("cli_enter_title_prompt"), curses.A_BOLD)
                    stdscr.refresh()
                    curses.echo()
                    title_bytes = stdscr.getstr(3, 2)
                    curses.noecho()
                    title = title_bytes.decode('utf-8').strip()
                    if not title:
                        stdscr.clear()
                        continue
                    if title == "0":
                        title = base_os
                    manager = GrubManager()
                    manager.set_default_kernel(title)
                    stdscr.addstr(5, 2, t("cli_grub_default_updated"), curses.A_BOLD)
                    stdscr.refresh()
                    stdscr.getch()
                    stdscr.clear()

        elif choice == 0:
            while True:
                k_opts = [
                    t("cli_view_installed"),
                    t("cli_compile_install"),
                    t("back"),
                ]
                k_choice = interactive_menu(stdscr, t("cli_kernels_title"), k_opts)
                if k_choice == 2:
                    break
                elif k_choice == 0:
                    manager = KernelManager()
                    installed = manager.get_installed_kernels()
                    if not installed:
                        interactive_menu(stdscr, t("cli_installed_kernels_title"), [t("back")], {0: t("cli_no_custom_kernels")})
                    else:
                        k_list = [f"Linux {k}" for k in installed]
                        k_list.append(t("back"))
                        interactive_menu(stdscr, t("cli_installed_kernels_title"), k_list)
                elif k_choice == 1:
                    stdscr.clear()
                    stdscr.addstr(1, 2, t("cli_fetching_upstream_kernels"), curses.A_BOLD)
                    stdscr.refresh()

                    manager = KernelManager()
                    try:
                        kernels = manager.fetch_available_kernels()
                        if not kernels:
                            interactive_menu(stdscr, t("cli_no_compatible_kernels"), [t("back")])
                            continue

                        flat_list = []
                        kernel_dicts = []
                        for series, versions in kernels.items():
                            for v in versions:
                                v_str = v.get("version", "Unknown")
                                moniker = v.get("moniker", "")
                                label = f"{v_str} [{moniker.upper()}]"
                                if v.get("iseol", False):
                                    label += " (EOL)"
                                flat_list.append(label)
                                kernel_dicts.append(v)

                        flat_list.append(t("back"))

                        sel_idx = interactive_menu(stdscr, t("cli_select_kernel_title"), flat_list)
                        if sel_idx == len(flat_list) - 1:
                            continue

                        version_dict = kernel_dicts[sel_idx]
                        version_str = version_dict.get("version")

                        make_default_choice = interactive_menu(stdscr, t("cli_set_as_default_prompt").format(version=version_str), [t("cli_yes"), t("cli_no")])
                        make_default = "y" if make_default_choice == 0 else "n"

                        menuconfig_choice = interactive_menu(stdscr, t("cli_customize_kconfig_prompt"), [t("cli_yes"), t("cli_no_use_default")])
                        use_menuconfig = (menuconfig_choice == 0)

                        curses.endwin()
                        print(t("cli_proceeding_compile").format(version=version_str))

                        vdict_repr = repr(version_dict)
                        cmd = ["sudo", sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}')
from puls_kernel_mgr.core.kernel import KernelManager
KernelManager().compile_and_install({vdict_repr}, use_menuconfig={use_menuconfig})
"""]
                        subprocess.run(cmd)

                        if make_default == "y":
                            g_cmd = ["sudo", sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}')
from puls_kernel_mgr.core.grub import GrubManager
GrubManager().set_kernel_next_boot("Advanced options for Debian GNU/Linux>Debian GNU/Linux, with Linux {version_str}")
"""]
                            subprocess.run(g_cmd)
                            print(t("cli_set_to_boot_next"))

                    except Exception as e:
                        curses.endwin()
                        print(t("cli_error_fetching_kernels").format(e=e))

                    input(t("cli_press_enter_return"))
                    stdscr.clear()


def main():
    import argparse
    tm = TranslationManager()
    t = tm.get

    parser = argparse.ArgumentParser(description="PULS Kernel Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    snap_parser = subparsers.add_parser("snapshot", help="Manage snapshots")
    snap_sub = snap_parser.add_subparsers(dest="snap_cmd")
    snap_sub.add_parser("create", help="Create a Timeshift snapshot")
    subparsers.add_parser("analyze-panic", help="Analyze kernel panic logs")
    subparsers.add_parser("generate-mok", help="Generate a Machine Owner Key")
    mok_enroll = subparsers.add_parser("enroll-mok", help="Enroll a Machine Owner Key")
    mok_enroll.add_argument("password", help="Password for enrollment")
    args = parser.parse_args()

    import os
    if os.geteuid() != 0:
        print("\n" + "="*50)
        print("    " + t("cli_warning_title"))
        print("="*50)
        for line in t("cli_warning_body").split("\n"):
            print(line)
        print("="*50)
        ans = input(t("cli_warning_prompt")).strip().lower()
        if ans not in ('y', 'e'):
            print(t("cli_exiting"))
            sys.exit(0)

        print("\n" + t("cli_launching"))
        curses.wrapper(curses_main)
        sys.exit(0)

    if args.command == "snapshot":
        if getattr(args, 'snap_cmd', None) != "create":
            print("Usage: puls-kernel-mgr snapshot create")
            sys.exit(1)
        from puls_kernel_mgr.core.safety import SafetyManager
        manager = SafetyManager()
        success, msg = manager.create_snapshot()
        print(msg)
        sys.exit(0 if success else 1)

    elif args.command == "analyze-panic":
        from puls_kernel_mgr.core.safety import SafetyManager
        manager = SafetyManager()
        print(manager.analyze_panic())
        sys.exit(0)

    elif args.command == "generate-mok":
        from puls_kernel_mgr.core.security import SecurityManager
        manager = SecurityManager()
        success, msg = manager.generate_mok()
        print(msg)
        sys.exit(0 if success else 1)

    elif args.command == "enroll-mok":
        from puls_kernel_mgr.core.security import SecurityManager
        manager = SecurityManager()
        success, msg = manager.enroll_mok(args.password)
        print(msg)
        sys.exit(0 if success else 1)

    try:
        curses.wrapper(curses_main)
    except KeyboardInterrupt:
        pass
    sys.exit(0)

if __name__ == "__main__":
    main()
