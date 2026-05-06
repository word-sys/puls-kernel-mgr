import subprocess
import os

class SecurityManager:
    def __init__(self):
        self.mok_dir = "/var/lib/shim-signed/mok"
        self.priv_key = os.path.join(self.mok_dir, "MOK.priv")
        self.der_key = os.path.join(self.mok_dir, "MOK.der")
        
    def generate_mok(self, common_name="FOSPX Custom Kernel Key"):
        if os.geteuid() != 0:
            return False, "Root privileges required to generate MOK."
        if not os.path.exists(self.mok_dir):
            try:
                os.makedirs(self.mok_dir, exist_ok=True)
            except Exception as e:
                return False, f"Failed to create MOK directory: {e}"
        if os.path.exists(self.priv_key) and os.path.exists(self.der_key):
            return True, "MOK keys already exist. Skipping generation."
            
        config = f"""
[ req ]
default_bits = 4096
distinguished_name = req_distinguished_name
prompt = no
string_mask = utf8only
x509_extensions = myexts

[ req_distinguished_name ]
O = FOSPX
CN = {common_name}
emailAddress = admin@localhost

[ myexts ]
basicConstraints=critical,CA:FALSE
keyUsage=digitalSignature
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid
"""
        config_path = "/tmp/mok_config.cnf"
        try:
            with open(config_path, "w") as f:
                f.write(config)
                
            cmd = [
                "openssl", "req", "-config", config_path,
                "-new", "-x509", "-newkey", "rsa:4096",
                "-nodes", "-days", "36500",
                "-outform", "DER",
                "-keyout", self.priv_key,
                "-out", self.der_key
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.chmod(self.priv_key, 0o600)
            return True, "Successfully generated Machine Owner Key (MOK)."
        except Exception as e:
            return False, f"Error generating MOK: {e}"
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)
                
    def enroll_mok(self, password):
        if os.geteuid() != 0:
            return False, "Root privileges required to enroll MOK."
            
        if not os.path.exists(self.der_key):
            return False, "MOK public key (DER) not found. Generate it first."
            
        try:
            input_data = f"{password}\n{password}\n"
            cmd = ["mokutil", "--import", self.der_key]
            result = subprocess.run(cmd, input=input_data, text=True, capture_output=True, check=True)
            return True, "MOK enrollment requested. PLEASE REBOOT to complete enrollment via MOKManager."
        except subprocess.CalledProcessError as e:
            if "already enrolled" in e.stdout or "already enrolled" in e.stderr:
                return True, "Key is already enrolled."
            return False, f"Failed to enroll MOK: {e.stderr or e.stdout}"
