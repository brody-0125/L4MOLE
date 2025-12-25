
import atexit
import logging
import os
import platform
import signal
import subprocess
import sys
import time
from typing import List

logger = logging.getLogger(__name__)

_managed_processes: List[subprocess.Popen] = []
_started_ollama: bool = False
_cleanup_registered: bool = False

def register_cleanup():
    global _cleanup_registered
    if _cleanup_registered:
        return

    atexit.register(cleanup_all)

    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

    _cleanup_registered = True
    logger.info("Cleanup handlers registered")

def _signal_handler(signum, _frame):
    logger.info(f"Received signal {signum}, cleaning up...")
    cleanup_all()
    sys.exit(0)

def set_started_ollama(started: bool) -> None:
    global _started_ollama
    _started_ollama = started

def get_ollama_processes() -> List[int]:
    pids = []
    system = platform.system()

    try:
        if system == "Darwin" or system == "Linux":
            result = subprocess.run(
                ["pgrep", "-f", "ollama"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            pids.append(int(line.strip()))
                        except ValueError:
                            pass
        elif system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq ollama.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if 'ollama' in line.lower():
                        parts = line.split(',')
                        if len(parts) >= 2:
                            try:
                                pid = int(parts[1].strip().strip('"'))
                                pids.append(pid)
                            except ValueError:
                                pass
    except Exception as e:
        logger.warning(f"Failed to get Ollama processes: {e}")

    return pids

def stop_ollama() -> bool:
    global _started_ollama

    if not _started_ollama:
        logger.info("Ollama was not started by us, leaving it running")
        return False

    logger.info("Stopping Ollama server...")
    system = platform.system()

    try:
        if system == "Darwin":
            subprocess.run(
                ["osascript", "-e", 'quit app "Ollama"'],
                capture_output=True,
                timeout=5
            )
            time.sleep(1)

        pids = get_ollama_processes()
        for pid in pids:
            try:
                if system == "Windows":
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/F"],
                        capture_output=True,
                        timeout=5
                    )
                else:
                    os.kill(pid, signal.SIGTERM)
                logger.info(f"Terminated Ollama process {pid}")
            except Exception as e:
                logger.warning(f"Failed to kill Ollama process {pid}: {e}")

        _started_ollama = False
        return True

    except Exception as e:
        logger.error(f"Failed to stop Ollama: {e}")
        return False

def cleanup_managed_processes() -> None:
    global _managed_processes

    for process in _managed_processes:
        try:
            if process.poll() is None:
                logger.info(f"Terminating managed process {process.pid}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing process {process.pid}")
                    process.kill()
        except Exception as e:
            logger.warning(f"Failed to terminate process: {e}")

    _managed_processes.clear()

def cleanup_all() -> None:
    logger.info("Performing application cleanup...")

    cleanup_managed_processes()

    stop_ollama()

    logger.info("Cleanup complete")

def get_app_data_dir() -> str:
    system = platform.system()

    if system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif system == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))

    app_dir = os.path.join(base, "L4MOLE")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir
