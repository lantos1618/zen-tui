#!/usr/bin/env python3
"""Integration test for the Zen packager; no microphone, window or model loading."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def run(*args, env=None, expect=0):
    result = subprocess.run([str(x) for x in args], env=env, capture_output=True, text=True)
    if result.returncode != expect:
        raise AssertionError(f'{args}: expected {expect}, got {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--sdk', type=Path, default=ROOT.parent / 'zen-parakeet/build/nemo-speech')
    parser.add_argument('--deny-sdk', action='store_true', help='Also run under sandbox-exec denying SDK reads (requires permission to apply a sandbox).')
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    source = ROOT / 'app/ZenCode.app'
    source_binary = source / 'Contents/MacOS/ZenCode'
    original = hashlib.sha256(source_binary.read_bytes()).digest()
    env = {k: v for k, v in os.environ.items() if not k.startswith('DYLD_')}
    env['ZEN_PARAKEET_MODEL'] = ''
    with tempfile.TemporaryDirectory(prefix='zen packaging ') as tmp:
        bundle = Path(tmp) / 'relocated app/ZenCode.app'
        run(ROOT / 'build/zen-package', source, sdk, bundle)
        run(ROOT / 'build/zen-package', source, sdk, bundle, expect=1)
        assert not (bundle / 'Contents/Resources/model-path.txt').exists()
        assert (bundle / 'Contents/Resources/NativeLicenses/LICENSE').exists()
        binary = bundle / 'Contents/MacOS/ZenCode'
        libs = list((bundle / 'Contents/Frameworks').glob('*.dylib'))
        assert libs, 'No native dependencies were packaged'
        for image in [binary, *libs]:
            assert 'LC_RPATH' not in run('/usr/bin/otool', '-l', image)
            for index, line in enumerate(run('/usr/bin/otool', '-L', image).splitlines()[1:]):
                dep = line.strip().split(' (compatibility version', 1)[0]
                if image != binary and index == 0:
                    assert dep == '@rpath/' + image.name
                elif dep.startswith(('/usr/lib/', '/System/Library/')):
                    continue
                else:
                    prefix = '@executable_path/../Frameworks/' if image == binary else '@loader_path/'
                    assert dep.startswith(prefix), (image, dep)
                    assert (bundle / 'Contents/Frameworks' / dep[len(prefix):]).is_file()
        run('/usr/bin/codesign', '--verify', '--deep', '--strict', bundle)
        run(binary, '--help', env=env)
        run(binary, '--check-config', env=env, expect=1)
        # Configuration lives outside the signed bundle. A dummy file tests path
        # persistence only; --check-config does not validate model contents.
        config_env = dict(env)
        config_env.pop('ZEN_PARAKEET_MODEL')
        user_dir = Path(tmp) / 'isolated user'
        user_dir.mkdir()
        config_env['HOME'] = str(user_dir)
        model = Path(tmp) / 'fixture model.gguf'
        model.write_bytes(b'configuration-only fixture')
        run(binary, '--set-model', model, env=config_env)
        config_file = user_dir / 'Library/Application Support/dev.zen.code/model-path.txt'
        assert config_file.read_text() == str(model)
        run(binary, '--check-config', env=config_env)
        second_model = Path(tmp) / 'replacement model.gguf'
        second_model.write_bytes(b'configuration-only replacement')
        run(binary, '--set-model', second_model, env=config_env)
        assert config_file.read_text() == str(second_model)
        run(binary, '--set-model', Path(tmp) / 'missing.gguf', env=config_env, expect=1)
        assert config_file.read_text() == str(second_model), 'Invalid path replaced saved configuration'
        override_env = dict(config_env, ZEN_PARAKEET_MODEL='')
        run(binary, '--check-config', env=override_env, expect=1)
        run('/usr/bin/codesign', '--verify', '--deep', '--strict', bundle)
        assert not (bundle / 'Contents/Resources/model-path.txt').exists()
        # A missing bundled library must fail instead of falling back to the SDK.
        dependency = bundle / 'Contents/Frameworks/libnemo_speech_asr_c.1.dylib'
        hidden = dependency.with_suffix('.hidden')
        dependency.rename(hidden)
        try:
            result = subprocess.run([str(binary), '--help'], env=env, capture_output=True)
            assert result.returncode != 0, 'Missing bundled library silently fell back to host SDK'
        finally:
            hidden.rename(dependency)
        if args.deny_sdk:
            escaped = str(sdk).replace('\\', '\\\\').replace('"', '\\"')
            profile = f'(version 1) (allow default) (deny file-read* (subpath "{escaped}"))'
            # Prove the policy actually blocks the SDK before trusting the test.
            blocked = subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, '/bin/cat', str(sdk / 'lib/libnemo_speech_asr_c.1.dylib')], capture_output=True)
            assert blocked.returncode != 0 and b'Operation not permitted' in blocked.stderr
            assert b'sandbox_apply' not in blocked.stderr, 'Host does not permit applying the test sandbox'
            run('/usr/bin/sandbox-exec', '-p', profile, binary, '--help', env=env)
            run('/usr/bin/sandbox-exec', '-p', profile, binary, '--check-config', env=env, expect=1)
        assert hashlib.sha256(source_binary.read_bytes()).digest() == original
        print(f'PASS: {len(libs)} bundled dependencies; relocation, signature, missing-library control, input preservation, user configuration preserves signature' + ('; SDK reads denied' if args.deny_sdk else ''))


if __name__ == '__main__':
    main()
