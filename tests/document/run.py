#!/usr/bin/env python3
"""Compile the pure Zen document model and exercise real file conflicts."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="zen-document-") as folder:
    work = Path(folder)
    (work / "main.zen").write_text((Path(__file__).parent / "main.zen").read_text())
    (work / "build.zen").write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
    macos = b.lib("macos", {src: Path(%s), libs: ["objc"], paths: []}).try();
    document = b.lib("document", {src: Path(%s), libs: [], paths: []}).try();
    b.exe("check", {src: Path("main.zen"), deps: [document, macos], language: "objective-c",
        frameworks: ["AppKit", "Foundation", "QuartzCore", "Metal", "AVFoundation", "AudioToolbox", "CoreFoundation"], out: Ok(Path("check"))}).try();
    Ok(())
}
''' % (json.dumps(str(ROOT.parent / "zen-macos/src/macos.zen")), json.dumps(str(ROOT / "src/document.zen"))))
    env = dict(os.environ, ZEN_STD=str(ROOT.parent / "zen/src"),
               ZEN_DOCUMENT_TEST_FILE=str(work / "document.txt"), CFLAGS="-O2 -Wno-parentheses-equality")
    subprocess.run([str(ROOT.parent / "zen/zen"), "build", "."], cwd=work,
                   env=env, check=True, timeout=120)
    subprocess.run([str(work / "check")], env=env, check=True, timeout=15)
