import os
import subprocess
import shutil

class KconfigManager:
    def __init__(self, src_dir):
        self.src_dir = src_dir

    def launch_menuconfig(self):
        if not os.path.exists(self.src_dir):
            return False, "Source directory does not exist."
            
        terminals = [
            ["gnome-terminal", "--", "bash", "-c"],
            ["x-terminal-emulator", "-e", "bash", "-c"],
            ["konsole", "-e", "bash", "-c"],
            ["xfce4-terminal", "-x", "bash", "-c"]
        ]
        
        selected_term = None
        for term in terminals:
            if shutil.which(term[0]):
                selected_term = term
                break
                
        if not selected_term:
            return False, "No supported terminal emulator found (tried gnome-terminal, konsole, etc)."
            
        try:
            cmd_str = f"cd {self.src_dir} && make menuconfig"
            full_cmd = selected_term + [cmd_str]
            subprocess.run(full_cmd, check=True)
            return True, "menuconfig closed."
        except subprocess.CalledProcessError as e:
            return False, f"Failed to run menuconfig: {e}"

    def set_reproducible_build_env(self):
        import datetime
        env = os.environ.copy()
        now = datetime.datetime.now()
        env["SOURCE_DATE_EPOCH"] = str(int(now.timestamp()))
        env["KBUILD_BUILD_TIMESTAMP"] = now.strftime("%Y-%m-%dT%H:%M:%S")
        
        env["KBUILD_BUILD_USER"] = "fospx"
        env["KBUILD_BUILD_HOST"] = "builder"
        return env
