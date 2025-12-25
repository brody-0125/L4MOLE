
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def get_base_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.absolute()

def get_resource_path(relative_path: str) -> Path:
    base_path = get_base_path()
    return base_path / relative_path

class SetupProgress:

    def __init__(self, use_gui: bool = False):
        self.use_gui = use_gui
        self.step = 0
        self.total_steps = 5

    def update(self, message: str, step: int = None):
        if step is not None:
            self.step = step
        progress = f"[{self.step}/{self.total_steps}]"
        print(f"{progress} {message}")

    def error(self, message: str):
        print(f"[오류] {message}")

    def success(self, message: str):
        print(f"[완료] {message}")

class L4MOLELauncher:

    REQUIRED_MODELS = ["nomic-embed-text"]
    OPTIONAL_MODELS = ["llava"]
    OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"

    def __init__(self):
        self.base_path = get_base_path()
        self.progress = SetupProgress()
        self.system = platform.system()
        self.ollama_was_running = False

    def run(self):
        print("=" * 50)
        print("    Local Semantic Explorer")
        print("=" * 50)
        print()

        try:
            self.progress.update("Checking Ollama...", 1)
            if not self._ensure_ollama():
                return False

            self.progress.update("Starting Ollama...", 2)
            if not self._start_ollama():
                return False

            self.progress.update("Checking AI models...", 3)
            if not self._ensure_models():
                return False

            self.progress.update("Setting up Python environment...", 4)
            if not self._setup_python_env():
                return False

            self.progress.update("Launching app...", 5)
            return self._launch_app()

        except KeyboardInterrupt:
            print("\nCancelled by user.")
            return False
        except Exception as e:
            self.progress.error(f"Unexpected error: {e}")
            return False

    def _get_ollama_path(self) -> str:
        ollama = shutil.which("ollama")
        if ollama:
            return ollama

        if self.system == "Darwin":
            paths = ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"]
        elif self.system == "Windows":
            local_app = os.environ.get("LOCALAPPDATA", "")
            program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
            paths = [
                os.path.join(local_app, "Programs", "Ollama", "ollama.exe"),
                os.path.join(local_app, "Ollama", "ollama.exe"),
                os.path.join(program_files, "Ollama", "ollama.exe"),
            ]
        else:
            paths = ["/usr/local/bin/ollama", "/usr/bin/ollama"]

        for path in paths:
            if os.path.exists(path):
                return path

        return None

    def _is_ollama_installed(self) -> bool:
        return self._get_ollama_path() is not None

    def _is_ollama_running(self) -> bool:
        ollama = self._get_ollama_path()
        if not ollama:
            return False

        try:
            result = subprocess.run(
                [ollama, "list"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def _install_ollama(self) -> bool:
        print("Ollama is not installed.")

        if self.system == "Darwin":
            if shutil.which("brew"):
                print("Installing Ollama using Homebrew...")
                try:
                    subprocess.run(["brew", "install", "ollama"], check=True)
                    return True
                except subprocess.CalledProcessError:
                    pass

        elif self.system == "Windows":
            if shutil.which("winget"):
                print("Installing Ollama using winget...")
                try:
                    subprocess.run(
                        ["winget", "install", "Ollama.Ollama", "-e"],
                        check=True
                    )
                    print("Installation complete. Restart may be required to update PATH.")
                    return True
                except subprocess.CalledProcessError:
                    pass

        print(f"\nPlease install Ollama manually.")
        print(f"Download page: {self.OLLAMA_DOWNLOAD_URL}")
        webbrowser.open(self.OLLAMA_DOWNLOAD_URL)
        input("\nPress Enter after installation to continue...")

        return self._is_ollama_installed()

    def _ensure_ollama(self) -> bool:
        if self._is_ollama_installed():
            print("  ✓ Ollama is installed.")
            return True

        return self._install_ollama()

    def _start_ollama(self) -> bool:
        if self._is_ollama_running():
            self.ollama_was_running = True
            print("  ✓ Ollama is already running.")
            return True

        print("  Starting Ollama server...")
        ollama = self._get_ollama_path()

        try:
            if self.system == "Darwin":
                try:
                    subprocess.run(["open", "-a", "Ollama"], check=True)
                except subprocess.CalledProcessError:
                    subprocess.Popen(
                        [ollama, "serve"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

            elif self.system == "Windows":
                local_app = os.environ.get("LOCALAPPDATA", "")
                app_paths = [
                    os.path.join(local_app, "Programs", "Ollama", "Ollama.exe"),
                    os.path.join(local_app, "Ollama", "Ollama.exe"),
                ]
                launched = False
                for app_path in app_paths:
                    if os.path.exists(app_path):
                        subprocess.Popen(
                            [app_path],
                            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                        )
                        launched = True
                        break

                if not launched:
                    subprocess.Popen(
                        [ollama, "serve"],
                        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                    )

            else:
                subprocess.Popen(
                    [ollama, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            for i in range(30):
                time.sleep(1)
                if self._is_ollama_running():
                    print("  ✓ Ollama server started.")
                    return True

            self.progress.error("Ollama server start timeout")
            return False

        except Exception as e:
            self.progress.error(f"Failed to start Ollama: {e}")
            return False

    def _get_installed_models(self) -> set:
        ollama = self._get_ollama_path()
        if not ollama:
            return set()

        try:
            result = subprocess.run(
                [ollama, "list"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return set()

            models = set()
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    model_name = line.split()[0].split(':')[0]
                    models.add(model_name)
            return models

        except Exception:
            return set()

    def _pull_model(self, model: str) -> bool:
        ollama = self._get_ollama_path()
        print(f"  Downloading model: {model} (this may take a while...)")

        try:
            process = subprocess.Popen(
                [ollama, "pull", model],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                line = line.strip()
                if line and ("pulling" in line.lower() or "%" in line):
                    print(f"    {line}", end='\r')

            process.wait()
            print()

            return process.returncode == 0

        except Exception as e:
            self.progress.error(f"Model download failed ({model}): {e}")
            return False

    def _ensure_models(self) -> bool:
        installed = self._get_installed_models()

        for model in self.REQUIRED_MODELS:
            if model in installed:
                print(f"  ✓ Model verified: {model}")
            else:
                if not self._pull_model(model):
                    return False
                print(f"  ✓ Model download complete: {model}")

        for model in self.OPTIONAL_MODELS:
            if model in installed:
                print(f"  ✓ Optional model available: {model}")
            else:
                print(f"  ○ Optional model not installed: {model} (for image search)")

        return True

    def _get_venv_python(self) -> Path:
        venv_dir = self.base_path / ".venv"
        if self.system == "Windows":
            return venv_dir / "Scripts" / "python.exe"
        return venv_dir / "bin" / "python"

    def _setup_python_env(self) -> bool:
        venv_dir = self.base_path / ".venv"
        venv_python = self._get_venv_python()
        requirements = self.base_path / "requirements.txt"

        if not venv_dir.exists():
            print("  Creating virtual environment...")
            try:
                import venv
                venv.create(str(venv_dir), with_pip=True)
            except Exception as e:
                self.progress.error(f"Failed to create virtual environment: {e}")
                return False

        if not venv_python.exists():
            self.progress.error("Python executable not found.")
            return False

        if requirements.exists():
            print("  Installing packages...")
            try:
                subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
                    capture_output=True,
                    check=True
                )
                subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-r", str(requirements)],
                    capture_output=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                self.progress.error(f"Package installation failed: {e}")
                return False

        print("  ✓ Python environment ready")
        return True

    def _launch_app(self) -> bool:
        venv_python = self._get_venv_python()
        main_script = self.base_path / "main.py"

        if not main_script.exists():
            self.progress.error("main.py not found.")
            return False

        print()
        print("=" * 50)
        print("  Starting Local Semantic Explorer...")
        print("  Closing this window will exit the application.")
        print("=" * 50)
        print()

        try:
            process = subprocess.run(
                [str(venv_python), str(main_script)],
                cwd=str(self.base_path)
            )

            self._cleanup()

            return process.returncode == 0

        except Exception as e:
            self.progress.error(f"Failed to launch app: {e}")
            return False

    def _cleanup(self):
        print()
        print("App exited.")

        if not self.ollama_was_running:
            print("Cleaning up Ollama server...")
            self._stop_ollama()

        print("Cleanup complete.")

    def _stop_ollama(self):
        try:
            if self.system == "Darwin":
                subprocess.run(
                    ["osascript", "-e", 'quit app "Ollama"'],
                    capture_output=True,
                    timeout=5
                )
            elif self.system == "Windows":
                subprocess.run(
                    ["taskkill", "/IM", "ollama.exe", "/F"],
                    capture_output=True,
                    timeout=5
                )
                subprocess.run(
                    ["taskkill", "/IM", "Ollama.exe", "/F"],
                    capture_output=True,
                    timeout=5
                )
            else:
                subprocess.run(
                    ["pkill", "-f", "ollama"],
                    capture_output=True,
                    timeout=5
                )
        except Exception as e:
            print(f"  Error stopping Ollama (ignored): {e}")

def main():
    launcher = L4MOLELauncher()
    success = launcher.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
