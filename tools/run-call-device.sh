#!/bin/bash
# Build/sign/install/run on a paired iPhone. Xcode manages provisioning.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# != 1 ]]; then
  echo 'Usage: tools/run-call-device.sh IPHONE_UDID' >&2
  echo 'Find devices with: xcrun devicectl list devices' >&2
  exit 2
fi
device="$1"
mkdir -p build
xcodebuild -project platforms/ios/ZenCall.xcodeproj -scheme ZenCall \
  -configuration Debug -destination "id=$device" \
  -derivedDataPath build/device-derived \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration \
  build > build/device-signed-build.log 2>&1 || {
    tail -50 build/device-signed-build.log
    exit 1
  }
bundle=build/device-derived/Build/Products/Debug-iphoneos/ZenCall.app
codesign --verify --strict "$bundle"
xcrun devicectl --timeout 60 device install app --device "$device" "$bundle"
xcrun devicectl --timeout 30 device process launch --device "$device" dev.zen.call.ios
