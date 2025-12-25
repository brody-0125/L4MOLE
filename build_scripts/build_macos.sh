#!/bin/bash
# L4MOLE macOS Build Script
# Creates a standalone .app bundle and DMG installer

set -e

# Configuration
APP_NAME="L4MOLE"
APP_VERSION="1.0.0"
BUNDLE_ID="com.l4mole.search"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
DMG_NAME="${APP_NAME}-${APP_VERSION}-macOS"

echo "========================================"
echo "  L4MOLE macOS Build Script"
echo "========================================"
echo ""
echo "Project: $PROJECT_DIR"
echo "Output:  $BUILD_DIR"
echo ""

# Check requirements
check_requirements() {
    echo "[1/6] Checking requirements..."

    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 is required"
        exit 1
    fi

    # Create venv if needed
    if [ ! -d "$PROJECT_DIR/.venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv "$PROJECT_DIR/.venv"
    fi

    # Use venv's pip directly (more reliable than activating)
    VENV_PIP="$PROJECT_DIR/.venv/bin/pip"
    VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

    "$VENV_PIP" install --upgrade pip > /dev/null 2>&1
    "$VENV_PIP" install pyinstaller > /dev/null 2>&1 || true

    echo "  ✓ Requirements satisfied"
}

# Clean previous builds
clean_build() {
    echo "[2/6] Cleaning previous builds..."
    rm -rf "$BUILD_DIR"
    rm -rf "$PROJECT_DIR/build"
    rm -f "$PROJECT_DIR"/*.spec
    mkdir -p "$BUILD_DIR"
    echo "  ✓ Clean complete"
}

# Create app bundle
create_app_bundle() {
    echo "[3/6] Creating app bundle..."

    VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

    cd "$PROJECT_DIR"

    # Create PyInstaller spec
    "$VENV_PYTHON" -m PyInstaller \
        --name="$APP_NAME" \
        --windowed \
        --onedir \
        --icon="resources/icon.icns" \
        --add-data="requirements.txt:." \
        --add-data="core:core" \
        --add-data="gui:gui" \
        --hidden-import="PyQt6" \
        --hidden-import="chromadb" \
        --hidden-import="ollama" \
        --hidden-import="pypdf" \
        --hidden-import="watchdog" \
        --osx-bundle-identifier="$BUNDLE_ID" \
        --noconfirm \
        launcher.py 2>/dev/null || {
            echo "  Note: PyInstaller build may have warnings, checking output..."
        }

    if [ -d "$BUILD_DIR/$APP_NAME.app" ]; then
        echo "  ✓ App bundle created"
    else
        echo "  Warning: App bundle not found, creating manually..."
        create_simple_app_bundle
    fi
}

# Create simple app bundle (fallback)
create_simple_app_bundle() {
    echo "  Creating simple app bundle..."

    # Create bundle structure
    mkdir -p "$APP_BUNDLE/Contents/MacOS"
    mkdir -p "$APP_BUNDLE/Contents/Resources"

    # Create Info.plist
    cat > "$APP_BUNDLE/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>Local Semantic Explorer</string>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleVersion</key>
    <string>$APP_VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$APP_VERSION</string>
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
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
</dict>
</plist>
EOF

    # Create launcher script
    cat > "$APP_BUNDLE/Contents/MacOS/launch" << 'LAUNCHER'
#!/bin/bash
# L4MOLE Launcher for macOS App Bundle

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOURCES_DIR="$SCRIPT_DIR/../Resources"
APP_DIR="$RESOURCES_DIR/app"

# Use bundled Python or system Python
if [ -d "$APP_DIR/.venv" ]; then
    PYTHON="$APP_DIR/.venv/bin/python"
else
    PYTHON=$(which python3)
fi

# Run the launcher
cd "$APP_DIR"
exec "$PYTHON" launcher.py
LAUNCHER

    chmod +x "$APP_BUNDLE/Contents/MacOS/launch"

    # Copy app files
    mkdir -p "$APP_BUNDLE/Contents/Resources/app"
    cp -r "$PROJECT_DIR/core" "$APP_BUNDLE/Contents/Resources/app/"
    cp -r "$PROJECT_DIR/gui" "$APP_BUNDLE/Contents/Resources/app/"
    cp "$PROJECT_DIR/main.py" "$APP_BUNDLE/Contents/Resources/app/"
    cp "$PROJECT_DIR/launcher.py" "$APP_BUNDLE/Contents/Resources/app/"
    cp "$PROJECT_DIR/requirements.txt" "$APP_BUNDLE/Contents/Resources/app/"

    # Copy or create venv (optional - for standalone)
    if [ -d "$PROJECT_DIR/.venv" ]; then
        echo "  Copying virtual environment..."
        cp -r "$PROJECT_DIR/.venv" "$APP_BUNDLE/Contents/Resources/app/.venv"
    fi

    echo "  ✓ Simple app bundle created"
}

# Create icon (if not exists)
create_icon() {
    echo "[4/6] Checking icon..."

    RESOURCES_DIR="$PROJECT_DIR/resources"
    mkdir -p "$RESOURCES_DIR"

    if [ ! -f "$RESOURCES_DIR/icon.icns" ]; then
        echo "  Note: No icon.icns found. Create one at resources/icon.icns for a custom icon."
    else
        cp "$RESOURCES_DIR/icon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns" 2>/dev/null || true
    fi

    echo "  ✓ Icon check complete"
}

# Create DMG
create_dmg() {
    echo "[5/6] Creating DMG installer..."

    DMG_PATH="$BUILD_DIR/$DMG_NAME.dmg"
    DMG_TEMP="$BUILD_DIR/dmg_temp"

    rm -f "$DMG_PATH"
    rm -rf "$DMG_TEMP"
    mkdir -p "$DMG_TEMP"

    # Copy app to temp
    cp -r "$APP_BUNDLE" "$DMG_TEMP/"

    # Create Applications symlink
    ln -s /Applications "$DMG_TEMP/Applications"

    # Create DMG
    hdiutil create -volname "$APP_NAME" \
        -srcfolder "$DMG_TEMP" \
        -ov -format UDZO \
        "$DMG_PATH" > /dev/null

    rm -rf "$DMG_TEMP"

    echo "  ✓ DMG created: $DMG_PATH"
}

# Summary
print_summary() {
    echo "[6/6] Build complete!"
    echo ""
    echo "========================================"
    echo "  Build Output"
    echo "========================================"
    echo ""
    echo "App Bundle: $APP_BUNDLE"
    if [ -f "$BUILD_DIR/$DMG_NAME.dmg" ]; then
        echo "DMG:        $BUILD_DIR/$DMG_NAME.dmg"
    fi
    echo ""
    echo "To install:"
    echo "  1. Open the DMG file"
    echo "  2. Drag L4MOLE to Applications"
    echo "  3. Run L4MOLE from Applications"
    echo ""
    echo "Note: On first run, you may need to:"
    echo "  - Allow the app in System Preferences > Security & Privacy"
    echo "  - Install Ollama if not already installed"
    echo ""
}

# Main
main() {
    check_requirements
    clean_build
    create_simple_app_bundle  # Use simple bundle for now
    create_icon
    create_dmg
    print_summary
}

main "$@"
