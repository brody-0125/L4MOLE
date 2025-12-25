@echo off
REM L4MOLE Windows Build Script
REM Creates a standalone executable and installer

setlocal enabledelayedexpansion

set APP_NAME=L4MOLE
set APP_VERSION=1.0.0
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set BUILD_DIR=%PROJECT_DIR%\dist
set INSTALLER_NAME=%APP_NAME%-%APP_VERSION%-Windows-Setup

echo ========================================
echo   L4MOLE Windows Build Script
echo ========================================
echo.
echo Project: %PROJECT_DIR%
echo Output:  %BUILD_DIR%
echo.

REM Check Python
echo [1/5] Checking requirements...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is required
    echo Please install Python from https://python.org
    exit /b 1
)
echo   - Python found

REM Create venv if needed
if not exist "%PROJECT_DIR%\.venv" (
    echo   Creating virtual environment...
    python -m venv "%PROJECT_DIR%\.venv"
)

REM Activate venv
call "%PROJECT_DIR%\.venv\Scripts\activate.bat"

REM Install PyInstaller
pip install --upgrade pip >nul 2>&1
pip install pyinstaller >nul 2>&1
echo   [OK] Requirements satisfied

REM Clean
echo [2/5] Cleaning previous builds...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%PROJECT_DIR%\build" rmdir /s /q "%PROJECT_DIR%\build"
del /q "%PROJECT_DIR%\*.spec" 2>nul
mkdir "%BUILD_DIR%"
echo   [OK] Clean complete

REM Build executable
echo [3/5] Building executable...
cd /d "%PROJECT_DIR%"

pyinstaller ^
    --name="%APP_NAME%" ^
    --windowed ^
    --onedir ^
    --icon="resources\icon.ico" ^
    --add-data="requirements.txt;." ^
    --add-data="core;core" ^
    --add-data="gui;gui" ^
    --add-data="main.py;." ^
    --hidden-import="PyQt6" ^
    --hidden-import="chromadb" ^
    --hidden-import="ollama" ^
    --hidden-import="pypdf" ^
    --hidden-import="watchdog" ^
    --noconfirm ^
    launcher.py

if not exist "%BUILD_DIR%\%APP_NAME%" (
    echo   Warning: PyInstaller build failed, creating portable version...
    call :create_portable
) else (
    echo   [OK] Executable created
)

REM Create portable zip
echo [4/5] Creating portable archive...
cd /d "%BUILD_DIR%"
if exist "%APP_NAME%" (
    powershell -Command "Compress-Archive -Path '%APP_NAME%' -DestinationPath '%APP_NAME%-%APP_VERSION%-Windows-Portable.zip' -Force"
    echo   [OK] Portable archive created
)

REM Create installer script (Inno Setup)
echo [5/5] Creating installer script...
call :create_inno_script

echo.
echo ========================================
echo   Build Complete
echo ========================================
echo.
echo Output files:
echo   - Portable: %BUILD_DIR%\%APP_NAME%-%APP_VERSION%-Windows-Portable.zip
echo   - Installer Script: %BUILD_DIR%\installer.iss
echo.
echo To create an installer:
echo   1. Install Inno Setup from https://jrsoftware.org/isinfo.php
echo   2. Open %BUILD_DIR%\installer.iss in Inno Setup
echo   3. Compile to create the installer
echo.

goto :eof

:create_portable
echo   Creating portable package...
mkdir "%BUILD_DIR%\%APP_NAME%"
xcopy /E /I /Y "%PROJECT_DIR%\core" "%BUILD_DIR%\%APP_NAME%\core" >nul
xcopy /E /I /Y "%PROJECT_DIR%\gui" "%BUILD_DIR%\%APP_NAME%\gui" >nul
copy /Y "%PROJECT_DIR%\main.py" "%BUILD_DIR%\%APP_NAME%\" >nul
copy /Y "%PROJECT_DIR%\launcher.py" "%BUILD_DIR%\%APP_NAME%\" >nul
copy /Y "%PROJECT_DIR%\requirements.txt" "%BUILD_DIR%\%APP_NAME%\" >nul

REM Create run script
echo @echo off > "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo cd /d "%%~dp0" >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo if not exist ".venv" ( >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo     echo Setting up environment... >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo     python -m venv .venv >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo     call .venv\Scripts\activate.bat >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo     pip install -r requirements.txt >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo ) else ( >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo     call .venv\Scripts\activate.bat >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo ) >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"
echo python launcher.py >> "%BUILD_DIR%\%APP_NAME%\Run L4MOLE.bat"

echo   [OK] Portable package created
goto :eof

:create_inno_script
REM Create Inno Setup script
(
echo ; L4MOLE Inno Setup Script
echo.
echo #define MyAppName "L4MOLE"
echo #define MyAppVersion "%APP_VERSION%"
echo #define MyAppPublisher "L4MOLE"
echo #define MyAppURL "https://github.com/l4mole/l4mole"
echo #define MyAppExeName "L4MOLE.exe"
echo.
echo [Setup]
echo AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
echo AppName={#MyAppName}
echo AppVersion={#MyAppVersion}
echo AppPublisher={#MyAppPublisher}
echo AppPublisherURL={#MyAppURL}
echo DefaultDirName={autopf}\{#MyAppName}
echo DefaultGroupName={#MyAppName}
echo OutputDir=%BUILD_DIR%
echo OutputBaseFilename=%INSTALLER_NAME%
echo Compression=lzma
echo SolidCompression=yes
echo WizardStyle=modern
echo PrivilegesRequired=lowest
echo.
echo [Languages]
echo Name: "english"; MessagesFile: "compiler:Default.isl"
echo Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
echo.
echo [Tasks]
echo Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
echo.
echo [Files]
echo Source: "%BUILD_DIR%\%APP_NAME%\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
echo.
echo [Icons]
echo Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
echo Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
echo Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
echo.
echo [Run]
echo Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
) > "%BUILD_DIR%\installer.iss"
echo   [OK] Inno Setup script created
goto :eof
