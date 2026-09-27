#!/usr/bin/env python3
"""Exercise editor policy against a native hidden App and real temporary file."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="zen-editor-") as folder:
    work = Path(folder)
    (work / "main.zen").write_text((Path(__file__).parent / "main.zen").read_text())
    libraries = {
        "macos": ROOT.parent / "zen-macos/src/macos.zen",
        "editor": ROOT / "src/editor.zen",
        "document": ROOT / "src/document.zen",
        "history": ROOT / "src/history.zen",
    }
    definitions = "\n".join(
        '    %s = b.lib(%s, {src: Path(%s), libs: %s, paths: []}).try();' %
        (name, json.dumps(name), json.dumps(str(path)), '["objc"]' if name == 'macos' else '[]')
        for name, path in libraries.items())
    (work / "build.zen").write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
%s
    b.exe("check", {src: Path("main.zen"), deps: [macos, editor, document, history], language: "objective-c",
        frameworks: ["AppKit", "Foundation", "QuartzCore", "Metal", "AVFoundation", "AudioToolbox", "CoreFoundation"], out: Ok(Path("check"))}).try();
    Ok(())
}
''' % definitions)
    env = dict(os.environ, ZEN_STD=str(ROOT.parent / "zen/src"), CFLAGS="-O2 -Wno-parentheses-equality")
    subprocess.run([str(ROOT.parent / "zen/zen"), "build", "."], cwd=work, env=env, check=True, timeout=120)
    document = work / "sample.zen"
    document.write_text("ab界\nnext")
    subprocess.run([str(work / "check"), "--file", str(document)], env=env, check=True, timeout=30)
    assert document.read_text() == "aX\n\t界\nnext"
    assert not list(work.glob("*.zen-*")), "atomic save leaked staging files"
