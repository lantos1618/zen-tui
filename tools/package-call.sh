#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
bundle=build/ZenCall.app
mkdir -p "$bundle/Contents/MacOS"
cat > "$bundle/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>ZenCall</string>
<key>CFBundleIdentifier</key><string>dev.zen.call.local</string>
<key>CFBundleName</key><string>Zen Call</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSCameraUsageDescription</key><string>Show a local camera preview in the Zen Call media experiment. No video is saved or sent.</string>
<key>NSMicrophoneUsageDescription</key><string>Transfer short microphone buffers to a local Zen actor and display their level. No audio is saved, sent over a network, or played.</string>
</dict></plist>
PLIST
/usr/bin/plutil -lint "$bundle/Contents/Info.plist"
/usr/bin/codesign --force --sign - "$bundle"
