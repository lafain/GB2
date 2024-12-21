import subprocess
import sys

def install_requirements():
    print("Installing dependencies...")
    
    # First install jsonschema directly
    print("Installing jsonschema...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "jsonschema", "--upgrade"])
    
    # Then install other requirements
    print("Installing other dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    print("Dependencies installed successfully!")

if __name__ == "__main__":
    install_requirements()