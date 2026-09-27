#!/usr/bin/env python3
"""Build the actual Zen actor and native library; always test an invalid model."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--zen', type=Path, default=ROOT.parent / 'zen/zen')
parser.add_argument('--sdk', type=Path, default=ROOT.parent / 'zen-parakeet/build/nemo-speech')
parser.add_argument('--model', type=Path)
parser.add_argument('--wav', type=Path,
                    help='Known 16 kHz mono float32 quick-brown-fox fixture from zen-parakeet/build/fixture.wav')
args = parser.parse_args()
if bool(args.model) != bool(args.wav):
    parser.error('--model and --wav must be provided together')
sdk = args.sdk.resolve()
if not (sdk / 'include/nemo_speech/asr.h').exists():
    parser.error('Install the NeMo native SDK first, or pass --sdk')

quote = lambda p: json.dumps(str(p))
with tempfile.TemporaryDirectory(prefix='zen-transcription-test-') as temporary:
    target = Path(temporary)
    (target / 'main.zen').write_text((Path(__file__).parent / 'main.zen').read_text())
    (target / 'build.zen').write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
    parakeet = b.lib("parakeet", {src: Path(%s), libs: ["nemo_speech_asr_c"], paths: [%s]}).try();
    transcription = b.lib("transcription", {src: Path(%s), libs: [], paths: []}).try();
    b.exe("check", {src: Path("main.zen"), deps: [parakeet,transcription], out: Ok(Path("check"))}).try();
    Ok(())
}
''' % (quote(ROOT.parent / 'zen-parakeet/src/parakeet.zen'), quote(sdk / 'lib'),
       quote(ROOT / 'src/transcription.zen')))
    env = dict(os.environ)
    env['ZEN_STD'] = str(ROOT.parent / 'zen/src')
    env['CFLAGS'] = shlex.join(['-O0', '-Wno-parentheses-equality', '-I' + str(sdk / 'include'),
                              '-Wl,-rpath,' + str(sdk / 'lib')])
    subprocess.run([str(args.zen.resolve()), 'build', '.'], cwd=target, env=env,
                   check=True, timeout=120)
    subprocess.run([str(target / 'check')], check=True, timeout=150)
    print('PASS: live scheduling, busy/final/stale handling, model error, admission, polling, repeated close')
    if args.model:
        subprocess.run([str(target / 'check'), str(args.model.resolve()), str(args.wav.resolve())],
                       check=True, timeout=150)
        print('PASS: real-model background transcription')
        subprocess.run([str(target / 'check'), str(args.model.resolve()), str(args.wav.resolve()), '--live'],
                       check=True, timeout=240)
        print('PASS: live partial contains quick; final contains quick brown fox and lazy dog')
    else:
        print('SKIP: real-model inference; supply --model MODEL.gguf --wav mono-float32.wav')
