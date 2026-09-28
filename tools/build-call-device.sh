#!/bin/bash
# Compile Zen for an actual arm64 iPhone. Signing is handled by Xcode.
set -euo pipefail
cd "$(dirname "$0")/.."
compiler="${ZEN_COMPILER:-$PWD/../zen/build/dev/actor-zen}"
std_root="${ZEN_STD:-$PWD/../zen/src}"
case "$compiler" in /*) ;; *) compiler="$PWD/$compiler" ;; esac
case "$std_root" in /*) ;; *) std_root="$PWD/$std_root" ;; esac
sdk=$(xcrun --sdk iphoneos --show-sdk-path)
mkdir -p build
(
    cd platforms/ios
    ZEN_STD="$std_root" CC="$(xcrun --find clang)" \
    CFLAGS="-O2 -g -target arm64-apple-ios17.0 -isysroot \"$sdk\"" \
    "$compiler" build zen-call-device
) > build/call-device-build.log 2>&1 || { tail -60 build/call-device-build.log; exit 1; }
xcrun vtool -show-build build/zen-call-device | grep -q 'platform IOS$'
echo "iPhone executable: $PWD/build/zen-call-device"
