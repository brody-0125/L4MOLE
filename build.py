
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "L4MOLE"
APP_VERSION = "1.0.0"
BUNDLE_ID = "com.l4mole.search"

PROJECT_DIR = Path(__file__).parent.absolute()
BUILD_DIR = PROJECT_DIR / "dist"
BUILD_SCRIPTS_DIR = PROJECT_DIR / "build_scripts"
RESOURCES_DIR = PROJECT_DIR / "resources"

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(message: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 50}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {message}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 50}{Colors.END}\n")

def print_step(step: int, total: int, message: str):
    print(f"{Colors.BLUE}[{step}/{total}]{Colors.END} {message}")

def print_success(message: str):
    print(f"{Colors.GREEN}  ✓ {message}{Colors.END}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}  ⚠ {message}{Colors.END}")

def print_error(message: str):
    print(f"{Colors.RED}  ✗ {message}{Colors.END}")

def ensure_resources():
    RESOURCES_DIR.mkdir(exist_ok=True)

    if not (RESOURCES_DIR / "icon.icns").exists():
        print_warning("No icon.icns found. Using placeholder.")

    if not (RESOURCES_DIR / "icon.ico").exists():
        print_warning("No icon.ico found. Using placeholder.")

def clean_build():
    print_step(1, 1, "Cleaning build artifacts...")

    paths_to_clean = [
        BUILD_DIR,
        PROJECT_DIR / "build",
        PROJECT_DIR / "__pycache__",
        PROJECT_DIR / "src" / "__pycache__",
        PROJECT_DIR / "gui" / "__pycache__",
        PROJECT_DIR / "tests" / "__pycache__",
    ]

    for spec in PROJECT_DIR.glob("*.spec"):
        spec.unlink()
        print(f"    Removed: {spec.name}")

    for path in paths_to_clean:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"    Removed: {path}")

    print_success("Clean complete")

def setup_venv():
    venv_dir = PROJECT_DIR / ".venv"

    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        print("  Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    try:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        print_warning("Failed to upgrade pip, continuing...")

    requirements = PROJECT_DIR / "requirements.txt"
    if requirements.exists():
        try:
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "-r", str(requirements)],
                capture_output=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print_warning(f"Some requirements may have failed: {e}")

    try:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "pyinstaller"],
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        print_warning("PyInstaller installation failed, will create simple bundle")

    return venv_python

def build_macos():
    print_header("Building for macOS")

    if platform.system() != "Darwin":
        print_warning("Not on macOS. Skipping macOS build.")
        return False

    return build_macos_python()

def build_macos_python():
    print_step(1, 5, "Setting up environment...")
    venv_python = setup_venv()
    print_success("Environment ready")

    print_step(2, 5, "Cleaning previous builds...")
    clean_build()
    BUILD_DIR.mkdir(exist_ok=True)

    print_step(3, 5, "Creating app bundle...")
    app_bundle = BUILD_DIR / f"{APP_NAME}.app"
    contents = app_bundle / "Contents"
    macos_dir = contents / "MacOS"
    resources = contents / "Resources"
    app_resources = resources / "app"

    for d in [macos_dir, resources, app_resources]:
        d.mkdir(parents=True, exist_ok=True)

    info_plist = contents / "Info.plist"
    info_plist.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>Local Semantic Explorer</string>
    <key>CFBundleIdentifier</key>
    <string>{BUNDLE_ID}</string>
    <key>CFBundleVersion</key>
    <string>{APP_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>{APP_VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
''')

    launcher = macos_dir / "launch"
    launcher.write_text('''#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/../Resources/app"

if [ -d "$APP_DIR/.venv" ]; then
    PYTHON="$APP_DIR/.venv/bin/python"
else
    PYTHON=$(which python3)
fi

cd "$APP_DIR"
exec "$PYTHON" launcher.py
''')
    launcher.chmod(0o755)

    for item in ["src", "gui"]:
        source = PROJECT_DIR / item
        dst = app_resources / item
        if source.exists():
            shutil.copytree(source, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    for item in ["main.py", "launcher.py", "requirements.txt"]:
        src = PROJECT_DIR / item
        if src.exists():
            shutil.copy2(src, app_resources)

    venv_src = PROJECT_DIR / ".venv"
    if venv_src.exists():
        print("    Copying virtual environment...")
        shutil.copytree(venv_src, app_resources / ".venv", symlinks=True)

    print_success("App bundle created")

    print_step(4, 5, "Creating DMG...")
    dmg_name = f"{APP_NAME}-{APP_VERSION}-macOS.dmg"
    dmg_path = BUILD_DIR / dmg_name
    dmg_temp = BUILD_DIR / "dmg_temp"

    if dmg_temp.exists():
        shutil.rmtree(dmg_temp)
    dmg_temp.mkdir()

    shutil.copytree(app_bundle, dmg_temp / f"{APP_NAME}.app", symlinks=True)
    os.symlink("/Applications", dmg_temp / "Applications")

    try:
        subprocess.run([
            "hdiutil", "create",
            "-volname", APP_NAME,
            "-srcfolder", str(dmg_temp),
            "-ov", "-format", "UDZO",
            str(dmg_path)
        ], check=True, capture_output=True)
        print_success(f"DMG created: {dmg_path}")
    except subprocess.CalledProcessError as e:
        print_warning(f"DMG creation failed: {e}")

    shutil.rmtree(dmg_temp)

    print_step(5, 5, "Build complete!")
    print(f"\n  App Bundle: {app_bundle}")
    print(f"  DMG:        {dmg_path}\n")

    return True

def build_windows():
    print_header("Building for Windows")

    if platform.system() == "Windows":
        return build_windows_native()
    else:
        print_warning("Not on Windows. Creating portable package instead.")
        return build_windows_portable()

def build_windows_native():
    build_script = BUILD_SCRIPTS_DIR / "build_windows.bat"

    if build_script.exists():
        try:
            subprocess.run(["cmd", "/c", str(build_script)], check=True)
            print_success("Windows build complete")
            return True
        except subprocess.CalledProcessError as e:
            print_error(f"Windows build failed: {e}")
            return False

    return build_windows_portable()

def build_windows_portable():
    print_step(1, 4, "Preparing Windows portable package...")

    BUILD_DIR.mkdir(exist_ok=True)
    win_dir = BUILD_DIR / f"{APP_NAME}-{APP_VERSION}-Windows-Portable"

    if win_dir.exists():
        shutil.rmtree(win_dir)
    win_dir.mkdir(parents=True)

    print_step(2, 4, "Copying application files...")

    for item in ["src", "gui"]:
        source = PROJECT_DIR / item
        dst = win_dir / item
        if source.exists():
            shutil.copytree(source, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    for item in ["main.py", "launcher.py", "requirements.txt"]:
        src = PROJECT_DIR / item
        if src.exists():
            shutil.copy2(src, win_dir)

    print_step(3, 4, "Creating launcher scripts...")

    run_bat = win_dir / "Run_L4MOLE.bat"
    run_bat_content = r"""@echo off
chcp 65001 > nul
title Local Semantic Explorer
cd /d "%~dp0"

echo ========================================
echo   Local Semantic Explorer
echo ========================================
echo.

REM Check for problematic path characters FIRST
set "CURRENT_PATH=%cd%"
echo %CURRENT_PATH% | findstr /C:"#" /C:"!" /C:"%%" /C:"&" >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] This folder path contains special characters.
    echo.
    echo Current path: %CURRENT_PATH%
    echo.
    echo Python virtual environment may fail to create.
    echo Please move this folder to a simple path like:
    echo   C:\L4MOLE
    echo   D:\Programs\L4MOLE
    echo.
    echo Avoid paths with:
    echo.
    choice /C YN /M "Try anyway (may fail)?"
    if errorlevel 2 goto :eof
)

REM Check if path is in OneDrive (sync issues)
echo %CURRENT_PATH% | findstr /I "OneDrive" >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] This folder is inside OneDrive.
    echo.
    echo OneDrive sync can cause issues with Python.
    echo Recommended: Move to C:\L4MOLE
    echo.
    choice /C YN /M "Try anyway?"
    if errorlevel 2 goto :eof
)

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed.
    echo Please install Python: https://python.org
    echo.
    pause
    exit /b 1
)

REM Setup venv if needed
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        echo.
        echo This is usually caused by:
        echo   1. Special characters in folder path (
        echo   2. OneDrive folder sync issues
        echo   3. Very long path names
        echo.
        echo Solution: Move this folder to C:\L4MOLE
        echo.
        pause
        exit /b 1
    )
    echo [SETUP] Installing packages... (this may take a while)
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install packages.
        echo Please check your internet connection.
        echo.
        pause
        exit /b 1
    )
    echo [SETUP] Done!
    echo.
) else (
    call .venv\Scripts\activate.bat
)

echo [START] Launching L4MOLE Search...
echo.
python launcher.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred.
    echo.
    pause
)
"""
    with open(run_bat, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(run_bat_content)

    setup_bat = win_dir / "Setup_First.bat"
    setup_bat_content = r"""@echo off
chcp 65001 > nul
title Local Semantic Explorer Setup
cd /d "%~dp0"

echo ========================================
echo   Local Semantic Explorer - First Time Setup
echo ========================================
echo.

REM Check current path for issues FIRST
set "CURRENT_PATH=%cd%"
echo [INFO] Current directory:
echo        %CURRENT_PATH%
echo.

REM Check for problematic path characters
set "PATH_OK=1"
echo %CURRENT_PATH% | findstr /C:"#" /C:"!" /C:"%%" /C:"&" >nul 2>&1
if %errorlevel% equ 0 set "PATH_OK=0"

echo %CURRENT_PATH% | findstr /I "OneDrive" >nul 2>&1
if %errorlevel% equ 0 set "PATH_OK=0"

if "%PATH_OK%"=="0" (
    echo ========================================
    echo   [WARNING] PATH ISSUE DETECTED
    echo ========================================
    echo.
    echo Your current folder path may cause problems.
    echo.
    echo Issues found:
    echo   - Special characters:
    echo   - Cloud sync folder: OneDrive, Dropbox
    echo   - Spaces in path
    echo.
    echo RECOMMENDED: Move this folder to:
    echo   C:\L4MOLE
    echo.
    echo This is a simple path that works reliably.
    echo.
    choice /C YN /M "Try setup anyway (may fail)?"
    if errorlevel 2 (
        echo.
        echo Please move the folder and try again.
        pause
        exit /b 0
    )
    echo.
)

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed.
    echo.
    echo Please install Python 3.9 or higher.
    echo Download: https://python.org/downloads
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    start https://python.org/downloads
    pause
    exit /b 1
)

echo [OK] Python is installed.
python --version
echo.

echo [1/3] Creating virtual environment...
if exist ".venv" (
    echo       Removing old virtual environment...
    rmdir /s /q ".venv" 2>nul
    timeout /t 2 >nul
)

REM Try creating venv with full python path
python -m venv .venv 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to create virtual environment.
    echo.
    echo Possible causes:
    echo   1. Python was not installed with "Add Python to PATH"
    echo   2. The folder path contains special characters or spaces
    echo   3. Antivirus is blocking the operation
    echo.
    echo Trying alternative method...
    echo.

    REM Try with virtualenv as fallback
    python -m pip install virtualenv 2>nul
    python -m virtualenv .venv 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Alternative method also failed.
        echo.
        echo Please try:
        echo   1. Move this folder to a simple path like C:\L4MOLE
        echo   2. Reinstall Python with "Add Python to PATH" checked
        echo   3. Temporarily disable antivirus
        echo.
        pause
        exit /b 1
    )
)
echo       Done!
echo.

echo [2/3] Installing packages... (this may take a while)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment activation script not found.
    pause
    exit /b 1
)

python -m pip install --upgrade pip 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Failed to upgrade pip, continuing...
)

python -m pip install -r requirements.txt 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install packages.
    echo.
    echo Please check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo       Done!
echo.

echo [3/3] Checking Ollama...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Ollama is not installed.
    echo        Ollama is required to run AI models.
    echo.
    echo        Opening Ollama download page...
    start https://ollama.com/download
    echo.
    echo        After installing Ollama, run this setup again or
    echo        just run "Run_L4MOLE.bat" directly.
) else (
    echo       Ollama is installed.
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Double-click "Run_L4MOLE.bat" to start the application.
echo.
pause
"""
    with open(setup_bat, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(setup_bat_content)

    print_step(4, 4, "Creating ZIP archive...")

    zip_path = BUILD_DIR / f"{APP_NAME}-{APP_VERSION}-Windows-Portable.zip"
    if zip_path.exists():
        zip_path.unlink()

    shutil.make_archive(
        str(BUILD_DIR / f"{APP_NAME}-{APP_VERSION}-Windows-Portable"),
        'zip',
        BUILD_DIR,
        f"{APP_NAME}-{APP_VERSION}-Windows-Portable"
    )

    print_success(f"Windows portable package created")
    print(f"\n  Folder: {win_dir}")
    print(f"  ZIP:    {zip_path}\n")

    return True

def build_current_platform():
    system = platform.system()

    if system == "Darwin":
        return build_macos()
    elif system == "Windows":
        return build_windows()
    else:
        print_error(f"Unsupported platform: {system}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="L4MOLE Build Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python build.py              Build for current platform
    python build.py --clean      Clean build artifacts
    python build.py --macos      Build for macOS
    python build.py --windows    Build for Windows
        """
    )

    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--macos", action="store_true", help="Build for macOS")
    parser.add_argument("--windows", action="store_true", help="Build for Windows")
    parser.add_argument("--all", action="store_true", help="Build for all platforms")

    args = parser.parse_args()

    print_header(f"L4MOLE Build System v{APP_VERSION}")

    ensure_resources()

    if args.clean:
        clean_build()
        return 0

    success = True

    if args.all:
        if platform.system() == "Darwin":
            success = build_macos() and success
        if platform.system() == "Windows":
            success = build_windows() and success
    elif args.macos:
        success = build_macos()
    elif args.windows:
        success = build_windows()
    else:
        success = build_current_platform()

    if success:
        print_header("Build Complete!")
        print(f"Output directory: {BUILD_DIR}\n")
    else:
        print_header("Build Failed")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
