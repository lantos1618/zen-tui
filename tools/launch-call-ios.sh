#!/bin/bash
# Build, package, install and open Zen Call directly in iOS Simulator.
set -euo pipefail
cd "$(dirname "$0")/.."
compiler="${ZEN_COMPILER:-../zen/build/dev/actor-zen}"
std_root="${ZEN_STD:-../zen/src}"
case "$compiler" in /*) ;; *) compiler="$PWD/$compiler" ;; esac
case "$std_root" in /*) ;; *) std_root="$PWD/$std_root" ;; esac
mkdir -p build
sdk=$(xcrun --sdk iphonesimulator --show-sdk-path)
(
  cd platforms/ios
  ZEN_STD="$std_root" CC="$(xcrun --find clang)" \
  CFLAGS="-O2 -target arm64-apple-ios17.0-simulator -isysroot \"$sdk\"" \
  "$compiler" build zen-call-ios
) > build/call-ios-build.log 2>&1 || { tail -60 build/call-ios-build.log; exit 1; }
bundle=build/ios/ZenCall.app
mkdir -p "$bundle"
xcrun vtool -show-build build/zen-call-ios | grep -q 'platform IOSSIMULATOR'
cp build/zen-call-ios "$bundle/ZenCall"
cp platforms/ios/Info.plist "$bundle/Info.plist"
plutil -lint "$bundle/Info.plist"
codesign --force --sign - "$bundle"
[[ "${1:-run}" == package ]] && exit 0
device="${ZEN_SIMULATOR_DEVICE:-}"
if [[ -z "$device" && -f ../zen-ui/build/simulator-device ]]; then device=$(cat ../zen-ui/build/simulator-device); fi
if [[ -z "$device" && -f build/call-simulator-device ]]; then device=$(cat build/call-simulator-device); fi
if [[ -z "$device" ]]; then
  device=$(xcrun simctl create 'Zen Call iPhone' com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro "${ZEN_IOS_RUNTIME:-com.apple.CoreSimulator.SimRuntime.iOS-26-2}")
  printf '%s\n' "$device" > build/call-simulator-device
fi
xcrun simctl bootstatus "$device" -b
open -a Simulator --args -CurrentDeviceUDID "$device"
xcrun simctl install "$device" "$bundle"
xcrun simctl launch --terminate-running-process "$device" dev.zen.call.ios
printf 'Zen Call is running on %s\n' "$device"
