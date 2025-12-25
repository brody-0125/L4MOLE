
import logging
import os
import platform
import shutil
import subprocess
import time

logger = logging.getLogger(__name__)

OLLAMA_STARTUP_TIMEOUT = 20
OLLAMA_LIST_TIMEOUT = 10

def get_ollama_cmd() -> str:
    path_ollama = shutil.which("ollama")
    if path_ollama is not None:
        return path_ollama

    system = platform.system()

    if system == "Darwin":
        macos_paths = ["/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"]
        for path in macos_paths:
            if os.path.exists(path):
                return path

    elif system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        user_profile = os.environ.get("USERPROFILE", "")

        windows_paths = [
            os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe"),
            os.path.join(local_app_data, "Ollama", "ollama.exe"),
            os.path.join(program_files, "Ollama", "ollama.exe"),
            os.path.join(user_profile, "AppData", "Local", "Programs", "Ollama", "ollama.exe"),
        ]

        for path in windows_paths:
            if os.path.exists(path):
                return path

    return "ollama"

def is_ollama_running() -> bool:
    ollama_cmd = get_ollama_cmd()

    try:
        subprocess.run(
            [ollama_cmd, "list"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=OLLAMA_LIST_TIMEOUT
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False

def _wait_for_ollama(timeout: int = OLLAMA_STARTUP_TIMEOUT) -> bool:
    for _ in range(timeout):
        if is_ollama_running():
            return True
        time.sleep(1)
    return False

def _start_ollama_macos(ollama_cmd: str) -> bool:
    try:
        subprocess.run(["open", "-a", "Ollama"], check=True)
        logger.info("Launched Ollama app. Waiting for it to be ready...")
        if _wait_for_ollama():
            logger.info("Ollama started successfully.")
            return True
    except Exception as err:
        logger.warning("Failed to launch Ollama app: %s", err)

    logger.info("Attempting to start 'ollama serve' in background...")
    try:
        subprocess.Popen(
            [ollama_cmd, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if _wait_for_ollama():
            logger.info("Ollama server started successfully.")
            return True
    except Exception as err:
        logger.error("Failed to start ollama serve: %s", err)

    return False

def _start_ollama_windows(ollama_cmd: str) -> bool:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")

    app_paths = [
        os.path.join(local_app_data, "Programs", "Ollama", "Ollama.exe"),
        os.path.join(local_app_data, "Ollama", "Ollama.exe"),
        os.path.join(program_files, "Ollama", "Ollama.exe"),
    ]

    for app_path in app_paths:
        if os.path.exists(app_path):
            try:
                logger.info("Starting Ollama from: %s", app_path)
                subprocess.Popen(
                    [app_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                )
                logger.info("Launched Ollama. Waiting for it to be ready...")
                if _wait_for_ollama():
                    logger.info("Ollama started successfully.")
                    return True
            except Exception as err:
                logger.warning("Failed to launch Ollama app: %s", err)
            break

    logger.info("Attempting to start 'ollama serve' in background...")
    try:
        subprocess.Popen(
            [ollama_cmd, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        )
        if _wait_for_ollama():
            logger.info("Ollama server started successfully.")
            return True
    except Exception as err:
        logger.error("Failed to start ollama serve: %s", err)

    return False

def _start_ollama_linux(ollama_cmd: str) -> bool:
    logger.info("Attempting to start 'ollama serve' in background...")
    try:
        subprocess.Popen(
            [ollama_cmd, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if _wait_for_ollama():
            logger.info("Ollama server started successfully.")
            return True
    except Exception as err:
        logger.error("Failed to start ollama serve: %s", err)

    return False

def start_ollama() -> bool:
    logger.info("Ollama is not running. Attempting to start...")
    ollama_cmd = get_ollama_cmd()
    system = platform.system()

    if system == "Darwin":
        return _start_ollama_macos(ollama_cmd)
    elif system == "Windows":
        return _start_ollama_windows(ollama_cmd)
    elif system == "Linux":
        return _start_ollama_linux(ollama_cmd)

    return False

def ensure_ollama_running() -> bool:
    if is_ollama_running():
        return True
    return start_ollama()
