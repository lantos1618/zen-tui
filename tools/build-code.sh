#!/bin/sh
# Build with an explicitly selected compiler; never silently select a stale seed.
set -eu
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ]; then
    echo 'Usage: tools/build-code.sh /absolute/path/to/zen-compiler' >&2
    exit 2
fi
case "$1" in
    /*) compiler=$1 ;;
    *) echo 'Compiler path must be absolute.' >&2; exit 2 ;;
esac
if [ ! -x "$compiler" ]; then
    echo "Compiler is not executable: $compiler" >&2
    exit 2
fi
workspace=$(cd .. && pwd)
sdk="$workspace/zen-parakeet/build/nemo-speech"
if [ ! -d "$sdk/include" ] || [ ! -d "$sdk/lib" ]; then
    echo 'Native speech SDK missing; follow zen-parakeet/README.md.' >&2
    exit 2
fi
mkdir -p build
# This inventory describes the inputs actually used, including dirty checkouts.
# It is not a claim that the workspace can be recreated from HEADs alone.
{
    date -u '+UTC %Y-%m-%dT%H:%M:%SZ'
    uname -sm
    shasum -a 256 "$compiler"
    for name in zen zen-tui zen-macos zen-audio zen-parakeet zen-voice zen-otel; do
        echo "Repository: $name"
        git -C "$workspace/$name" rev-parse HEAD
        git -C "$workspace/$name" status --short
    done
} > build/code-build-inputs.txt
ZEN_STD="$workspace/zen/src" \
CFLAGS="${CFLAGS:--O2} -I\"$sdk/include\" -Wl,-rpath,\"$sdk/lib\"" \
    "$compiler" build zen-code
shasum -a 256 app/ZenCode.app/Contents/MacOS/ZenCode >> build/code-build-inputs.txt
printf '%s\n' 'Built Zen Code; input inventory: build/code-build-inputs.txt'
