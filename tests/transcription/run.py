#!/usr/bin/env python3
"""Run the reusable voice contract and the app's continuous history integration."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--zen', type=Path, default=ROOT.parent / 'zen/zen')
parser.add_argument('--sdk', type=Path, default=ROOT.parent / 'zen-parakeet/build/nemo-speech')
parser.add_argument('--model', type=Path)
parser.add_argument('--wav', type=Path,
                    help='Known 16 kHz mono float32 quick-brown-fox fixture')
args = parser.parse_args()
if bool(args.model) != bool(args.wav):
    parser.error('--model and --wav must be provided together')
sdk = args.sdk.resolve()
command = [sys.executable, str(ROOT.parent / 'zen-voice/tests/run.py'),
           '--zen', str(args.zen.resolve()), '--sdk', str(sdk)]
if args.model:
    command += ['--model', str(args.model.resolve()), '--wav', str(args.wav.resolve())]
subprocess.run(command, check=True)
quote = lambda p: json.dumps(str(p))
with tempfile.TemporaryDirectory(prefix='zen-history-test-') as temporary:
    target = Path(temporary)
    (target / 'main.zen').write_text((Path(__file__).parent / 'continuous_state.zen').read_text())
    (target / 'build.zen').write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
    parakeet = b.lib("parakeet", {src: Path(%s), libs: ["nemo_speech_asr_c"], paths: [%s]}).try();
    voice = b.lib("voice", {src: Path(%s), libs: [], paths: []}).try();
    history = b.lib("history", {src: Path(%s), libs: [], paths: []}).try();
    b.exe("check", {src: Path("main.zen"), deps: [parakeet,voice,history], out: Ok(Path("check"))}).try();
    Ok(())
}
''' % (quote(ROOT.parent / 'zen-parakeet/src/parakeet.zen'), quote(sdk / 'lib'),
       quote(ROOT.parent / 'zen-voice/src/voice.zen'), quote(ROOT / 'src/history.zen')))
    env = dict(os.environ)
    env['ZEN_STD'] = str(ROOT.parent / 'zen/src')
    env['CFLAGS'] = shlex.join(['-O0', '-Wno-parentheses-equality', '-I' + str(sdk / 'include'),
                              '-Wl,-rpath,' + str(sdk / 'lib')])
    subprocess.run([str(args.zen.resolve()), 'build', '.'], cwd=target, env=env,
                   check=True, timeout=120)
    subprocess.run([str(target / 'check')], check=True, timeout=15)
    print('PASS: 77.5-second continuous segmentation, exact tail accounting, history, and UTF-8 bounds')
