import sys
import curses
from fospx_kernel_mgr.core.grub import GrubManager
from fospx_kernel_mgr.core.kernel import KernelManager

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
    from fospx_kernel_mgr.core.grub import GrubManager
    from fospx_kernel_mgr.core.kernel import KernelManager
    from fospx_kernel_mgr.core.safety import SafetyManager
    from fospx_kernel_mgr.core.security import SecurityManager
    import subprocess, os, sys
    
    while True:
        main_options = ["Kernels", "Boot Manager", "Safety & Security", "About", "Exit"]
        
        # Build context dict
        g_man = GrubManager()
        cfg = g_man.read_default_config()
        grub_context = "View and modify your GRUB boot entries.\n\nCurrent Configuration:"
        grub_context += f"\n- Default Entry: {cfg.get('GRUB_DEFAULT', '0')}"
        grub_context += f"\n- Timeout: {cfg.get('GRUB_TIMEOUT', '5')}s"
        
        entries = g_man.get_grub_entries()
        grub_context += "\n\nLive GRUB Order:"
        base_os = entries[0]['title'] if entries else "0"
        for e in entries:
            grub_context += f"\n- {e['title'][:40]}"
            if e.get('type') == 'submenu':
                for child in e.get('children', []):
                    grub_context += f"\n   > {child['title'][:35]}"
            
        k_man = KernelManager()
        installed = k_man.get_installed_kernels()
        kernels_context = "Kernels Management\n\nInstalled Kernels:"
        if not installed:
            kernels_context += "\n- No custom kernels found."
        else:
            for k in installed:
                kernels_context += f"\n- Linux {k}"
                
        safety_context = "Safety & Security\n\n- Manage system snapshots\n- Configure Secure Boot (MOK)\n- Analyze kernel panics"
        
        context_dict = {
            0: kernels_context,
            1: grub_context,
            2: safety_context,
            3: "View FOSPX Kernel Manager\nVersion and License information.",
            4: "Exit application."
        }
        
        choice = interactive_menu(stdscr, "=== FOSPX Kernel Manager ===", main_options, context_dict)
        
        if choice == 4:
            break
        elif choice == 3:
            about_opts = ["Back"]
            title = "--- About ---"
            about_context = "FOSPX Kernel/GRUB Manager\nVersion: 0.1.0\n\nDeveloper: Barın Güzeldemirci\nContact: baringuzeldemir@gmail.com\n\nLicense: GPL-3.0-or-later\nThis program is free software."
            interactive_menu(stdscr, title, about_opts, {0: about_context})
        elif choice == 2:
            while True:
                safety_opts = ["Install Dependencies", "Create Snapshot", "Generate MOK", "Enroll MOK", "Analyze Panics", "Back"]
                s_choice = interactive_menu(stdscr, "--- Safety & Security ---", safety_opts)
                if s_choice == 5:
                    break
                elif s_choice == 0:
                    curses.endwin()
                    print("Installing dependencies...")
                    subprocess.run(["sudo", sys.executable, "-c", "from fospx_kernel_mgr.core.safety import SafetyManager; SafetyManager().install_dependencies()"])
                    input("Press Enter to continue...")
                    stdscr.clear()
                elif s_choice == 1:
                    curses.endwin()
                    print("Creating snapshot...")
                    subprocess.run(["sudo", sys.executable, "-c", "from fospx_kernel_mgr.core.safety import SafetyManager; sm=SafetyManager(); _,msg=sm.create_snapshot(); print(msg)"])
                    input("Press Enter to continue...")
                    stdscr.clear()
                elif s_choice == 2:
                    curses.endwin()
                    print("Generating MOK...")
                    subprocess.run(["sudo", sys.executable, "-c", "from fospx_kernel_mgr.core.security import SecurityManager; sm=SecurityManager(); _,msg=sm.generate_mok(); print(msg)"])
                    input("Press Enter to continue...")
                    stdscr.clear()
                elif s_choice == 3:
                    curses.endwin()
                    import getpass
                    pw = getpass.getpass("Enter new MOK password: ")
                    subprocess.run(["sudo", sys.executable, "-c", f"from fospx_kernel_mgr.core.security import SecurityManager; sm=SecurityManager(); _,msg=sm.enroll_mok('{pw}'); print(msg)"])
                    input("Press Enter to continue...")
                    stdscr.clear()
                elif s_choice == 4:
                    curses.endwin()
                    sm = SafetyManager()
                    print(sm.analyze_panic())
                    input("Press Enter to continue...")
                    stdscr.clear()
                    
        elif choice == 1:
            while True:
                grub_opts = ["Set Default Boot Entry", "Configure GRUB (Interactive)", "Restore Factory Defaults", "Back"]
                g_context_dict = {
                    0: grub_context,
                    1: grub_context,
                    2: grub_context,
                    3: grub_context
                }
                g_choice = interactive_menu(stdscr, "--- Boot Manager ---", grub_opts, g_context_dict)
                if g_choice == 3:
                    break
                elif g_choice == 2:
                    curses.endwin()
                    manager = GrubManager()
                    snaps = manager.backup.list_snapshots()
                    if snaps:
                        manager.backup.restore_snapshot(snaps[-1]) # Restore oldest
                        print("Restored original defaults. Press Enter.")
                    else:
                        print("No backups found.")
                    input()
                    stdscr.clear()
                elif g_choice == 1:
                    stdscr.clear()
                    stdscr.addstr(1, 2, "Enter GRUB Timeout (empty to cancel): ", curses.A_BOLD)
                    stdscr.refresh()
                    curses.echo()
                    timeout_bytes = stdscr.getstr(3, 2)
                    timeout = timeout_bytes.decode('utf-8').strip()
                    if not timeout:
                        curses.noecho()
                        stdscr.clear()
                        continue
                    stdscr.clear()
                    stdscr.addstr(1, 2, "Enter CMDLINE_DEFAULT (empty to keep): ", curses.A_BOLD)
                    stdscr.refresh()
                    cmdline_bytes = stdscr.getstr(3, 2)
                    curses.noecho()
                    cmdline = cmdline_bytes.decode('utf-8').strip()
                    if not cmdline:
                        cmdline = cfg.get("GRUB_CMDLINE_LINUX_DEFAULT", "")
                    curses.endwin()
                    manager = GrubManager()
                    manager.write_advanced_config({"GRUB_TIMEOUT": timeout, "GRUB_CMDLINE_LINUX_DEFAULT": cmdline})
                    print("GRUB updated. Press Enter.")
                    input()
                    stdscr.clear()
                elif g_choice == 0:
                    stdscr.clear()
                    stdscr.addstr(1, 2, "Enter exact title (or '0' for Base OS, empty to cancel): ", curses.A_BOLD)
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
                    stdscr.addstr(5, 2, "Updated GRUB default. Press any key to continue.", curses.A_BOLD)
                    stdscr.refresh()
                    stdscr.getch()
                    stdscr.clear()
                    
        elif choice == 0:
            while True:
                k_opts = ["View Installed Kernels", "Compile & Install Upstream Kernel", "Back"]
                k_choice = interactive_menu(stdscr, "--- Kernels ---", k_opts)
                if k_choice == 2:
                    break
                elif k_choice == 0:
                    manager = KernelManager()
                    installed = manager.get_installed_kernels()
                    if not installed:
                        interactive_menu(stdscr, "--- Installed Kernels ---", ["Back"], {0: "No local custom kernels found."})
                    else:
                        k_list = [f"Linux {k}" for k in installed]
                        k_list.append("Back")
                        interactive_menu(stdscr, "--- Installed Kernels ---", k_list)
                elif k_choice == 1:
                    stdscr.clear()
                    stdscr.addstr(1, 2, "Fetching kernels from kernel.org...", curses.A_BOLD)
                    stdscr.refresh()
                    
                    manager = KernelManager()
                    try:
                        kernels = manager.fetch_available_kernels()
                        if not kernels:
                            interactive_menu(stdscr, "No compatible kernels found.", ["Back"])
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
                        
                        flat_list.append("Back")
                        
                        sel_idx = interactive_menu(stdscr, "--- Select Kernel to Install ---", flat_list)
                        if sel_idx == len(flat_list) - 1:
                            continue # Back
                            
                        version_dict = kernel_dicts[sel_idx]
                        version_str = version_dict.get("version")
                        
                        make_default_choice = interactive_menu(stdscr, f"Set {version_str} as default GRUB entry?", ["Yes", "No"])
                        make_default = "y" if make_default_choice == 0 else "n"
                        
                        menuconfig_choice = interactive_menu(stdscr, f"Customize Kernel Configuration (menuconfig)?", ["Yes", "No (Use default)"])
                        use_menuconfig = (menuconfig_choice == 0)
                        
                        curses.endwin()
                        print(f"\nProceeding to compile and install {version_str}...")
                        
                        vdict_repr = repr(version_dict)
                        cmd = ["sudo", sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}')
from fospx_kernel_mgr.core.kernel import KernelManager
KernelManager().compile_and_install({vdict_repr}, use_menuconfig={use_menuconfig})
"""]
                        subprocess.run(cmd)
                        
                        if make_default == "y":
                            g_cmd = ["sudo", sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}')
from fospx_kernel_mgr.core.grub import GrubManager
GrubManager().set_kernel_next_boot("Advanced options for Debian GNU/Linux>Debian GNU/Linux, with Linux {version_str}")
"""]
                            subprocess.run(g_cmd)
                            print("Set to boot this kernel on next restart.")
                        
                    except Exception as e:
                        curses.endwin()
                        print(f"Error fetching kernels: {e}")
                    
                    input("\nPress Enter to return to main menu...")
                    stdscr.clear()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="FOSPX Kernel Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    snap_parser = subparsers.add_parser("snapshot", help="Manage snapshots")
    snap_sub = snap_parser.add_subparsers(dest="snap_cmd")
    snap_sub.add_parser("create", help="Create a Timeshift snapshot")
    subparsers.add_parser("analyze-panic", help="Analyze kernel panic logs")
    mok_gen = subparsers.add_parser("generate-mok", help="Generate a Machine Owner Key")
    mok_enroll = subparsers.add_parser("enroll-mok", help="Enroll a Machine Owner Key")
    mok_enroll.add_argument("password", help="Password for enrollment")
    args = parser.parse_args()
    
    import os
    if os.geteuid() != 0:
        print("\n" + "="*50)
        print("    SYSTEM SECURITY & STABILITY WARNING")
        print("="*50)
        print("Modifying the Linux kernel is an advanced operation")
        print("that can cause system instability, data loss, or")
        print("prevent your system from booting.")
        print("\nPlease ensure you have backups or snapshots")
        print("configured before proceeding.")
        print("="*50)
        ans = input("Do you understand the risks and wish to continue? (y/N): ").strip().lower()
        if ans != 'y':
            print("Exiting.")
            sys.exit(0)
            
        print("\nLaunching FOSPX Kernel/GRUB Manager...")
        curses.wrapper(curses_main)
        sys.exit(0)
            
    if args.command == "snapshot":
        if getattr(args, 'snap_cmd', None) != "create":
            print("Usage: fospx-kernel-mgr snapshot create")
            sys.exit(1)
        from fospx_kernel_mgr.core.safety import SafetyManager
        manager = SafetyManager()
        success, msg = manager.create_snapshot()
        print(msg)
        sys.exit(0 if success else 1)
        
    elif args.command == "analyze-panic":
        from fospx_kernel_mgr.core.safety import SafetyManager
        manager = SafetyManager()
        print(manager.analyze_panic())
        sys.exit(0)
        
    elif args.command == "generate-mok":
        from fospx_kernel_mgr.core.security import SecurityManager
        manager = SecurityManager()
        success, msg = manager.generate_mok()
        print(msg)
        sys.exit(0 if success else 1)
        
    elif args.command == "enroll-mok":
        from fospx_kernel_mgr.core.security import SecurityManager
        manager = SecurityManager()
        success, msg = manager.enroll_mok(args.password)
        print(msg)
        sys.exit(0 if success else 1)
        
    #interactive mode
    try:
        curses.wrapper(curses_main)
    except KeyboardInterrupt:
        pass
    sys.exit(0)

if __name__ == "__main__":
    main()
