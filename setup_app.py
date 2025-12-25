
import os
import platform
import shutil
import subprocess
import sys
import venv
import webbrowser

def get_base_path():
    return os.path.dirname(os.path.abspath(__file__))

def check_ollama_installed():
    return shutil.which("ollama") is not None

def install_ollama():
    print("Ollama CLI not found.")

    if platform.system() == "Windows":
        if shutil.which("winget"):
            print("Attempting to install via winget...")
            try:
                subprocess.run(["winget", "install", "Ollama.Ollama", "-e"], check=True)
                print("Ollama installed successfully.")
                return True
            except subprocess.CalledProcessError:
                print("Winget installation failed.")

    elif platform.system() == "Darwin":
        if shutil.which("brew"):
            print("Attempting to install via Homebrew...")
            try:
                subprocess.run(["brew", "install", "ollama"], check=True)
                print("Ollama installed successfully.")
                return True
            except subprocess.CalledProcessError:
                print("Homebrew installation failed.")

    print("Opening Ollama download page...")
    webbrowser.open("https://ollama.com/download")
    input("Please install Ollama and press Enter to continue...")
    return check_ollama_installed()

def ensure_ollama_running():
    try:
        sys.path.insert(0, get_base_path())
        from src.infrastructure.ollama_utils import (
            ensure_ollama_running as _ensure,
        )
        return _ensure()
    except ImportError:
        pass

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            return True

        if platform.system() == "Darwin":
            subprocess.run(["open", "-a", "Ollama"], check=False)
        elif platform.system() == "Windows":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        import time
        for _ in range(10):
            time.sleep(1)
            result = subprocess.run(["ollama", "list"], capture_output=True)
            if result.returncode == 0:
                return True

        return False

    except Exception as e:
        print(f"Warning: Could not verify Ollama: {e}")
        return False

def pull_models():
    if not ensure_ollama_running():
        print("Warning: Could not start Ollama. Please start it manually.")
        return

    models = ["nomic-embed-text"]

    for model in models:
        print(f"Checking/Pulling model: {model}...")
        try:
            subprocess.run(["ollama", "pull", model], check=True)
            print(f"  ✓ Model ready: {model}")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Failed to pull model {model}: {e}")

def create_venv(base_path):
    venv_dir = os.path.join(base_path, ".venv")
    if not os.path.exists(venv_dir):
        print(f"Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)
        print("  ✓ Virtual environment created")
    return venv_dir

def get_venv_python(base_path):
    venv_dir = os.path.join(base_path, ".venv")
    if platform.system() == "Windows":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        return os.path.join(venv_dir, "bin", "python")

def install_requirements():
    print("Installing Python packages...")
    base_path = get_base_path()
    req_file = os.path.join(base_path, "requirements.txt")
    venv_python = get_venv_python(base_path)

    if not os.path.exists(req_file):
        print(f"  ✗ requirements.txt not found at {req_file}")
        return False

    try:
        subprocess.check_call(
            [venv_python, "-m", "pip", "install", "--upgrade", "pip"],
            stdout=subprocess.DEVNULL
        )
        subprocess.check_call(
            [venv_python, "-m", "pip", "install", "-r", req_file]
        )
        print("  ✓ All packages installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed to install requirements: {e}")
        return False

def main():
    print("=" * 50)
    print("  Local Semantic Explorer - Setup")
    print("=" * 50)
    print()

    base_path = get_base_path()

    print("[1/3] Setting up Python environment...")
    create_venv(base_path)

    print("\n[2/3] Checking Ollama...")
    if not check_ollama_installed():
        if not install_ollama():
            print("\n✗ Ollama is required for this application.")
            return 1

    print("  ✓ Ollama is installed")
    pull_models()

    print("\n[3/3] Installing Python packages...")
    if not install_requirements():
        print("\n✗ Failed to install packages.")
        return 1

    print()
    print("=" * 50)
    print("  Setup Complete!")
    print("=" * 50)
    print()
    print("You can now run the application:")
    print("  python main.py")
    print("  ./run_app.sh")
    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
