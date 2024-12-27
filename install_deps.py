import subprocess
import sys

def install_dependencies():
    print("Installing dependencies...")
    
    # Core dependencies from requirements.txt
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Additional dependencies for vision and display
    additional_deps = [
        "pytesseract",
        "screeninfo",
        "opencv-python",
        "pywin32"  # This includes win32api
    ]
    
    for dep in additional_deps:
        print(f"Installing {dep}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to install {dep}: {e}")
            
    print("Dependencies installed successfully!")

if __name__ == "__main__":
    install_dependencies()