#!/usr/bin/env python3
"""Synthetic voice spans; no microphone/model, verify disabled native clocks."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser()
p.add_argument('--zen', type=Path, required=True)
p.add_argument('--app', type=Path, help='Optional built native app: verify early-error cleanup before a window opens')
p.add_argument('--render-smoke', action='store_true', help='Also open the app for a bounded native render/cleanup check')
args = p.parse_args()
if args.render_smoke and args.app is None:
    p.error('--render-smoke requires --app')
quote = lambda value: json.dumps(str(value))
with tempfile.TemporaryDirectory(prefix='zen-telemetry-') as folder:
    work = Path(folder)
    (work / 'main.zen').write_text((Path(__file__).parent / 'main.zen').read_text())
    (work / 'clock_probe.h').write_text('''#pragma once
#include <time.h>
#include <stdint.h>
#include <pthread.h>
static uint64_t clock_calls, worker_calls;
static void reset(void) { clock_calls = 0; worker_calls = 0; }
static uint64_t workers(void) { return worker_calls; }
static int traced_pthread_create(pthread_t *thread, const pthread_attr_t *attr, void *(*entry)(void *), void *arg) {
    worker_calls++;
    return pthread_create(thread, attr, entry, arg);
}
#define pthread_create traced_pthread_create
static uint64_t count(void) { return clock_calls; }
static int traced_clock_gettime(clockid_t id, struct timespec *ts) {
    clock_calls++;
    return clock_gettime(id, ts);
}
#define clock_gettime traced_clock_gettime
''')
    sdk = ROOT.parent / 'zen-parakeet/build/nemo-speech'
    libraries = [
        ('macos', ROOT.parent / 'zen-macos/src/macos.zen', ['objc'], []),
        ('parakeet', ROOT.parent / 'zen-parakeet/src/parakeet.zen', ['nemo_speech_asr_c'], [str(sdk / 'lib')]),
        ('voice', ROOT.parent / 'zen-voice/src/voice.zen', [], []),
        ('otel', ROOT.parent / 'zen-otel/src/otel.zen', [], []),
        ('observability', ROOT / 'src/observability.zen', [], []),
    ]
    lines = ['Builder, BuildError = std.build', 'build = (b :: Builder) Res<(), BuildError> {']
    for name, path, libs, paths in libraries:
        lines.append(f'{name} = b.lib({quote(name)}, {{src: Path({quote(path)}), libs: {json.dumps(libs)}, paths: {json.dumps(paths)}}}).try();')
    lines += ['b.exe("check", {src: Path("main.zen"), deps: [macos, parakeet, voice, otel, observability], out: Ok(Path("check"))}).try();', 'Ok(())', '}']
    (work / 'build.zen').write_text('\n'.join(lines))
    env = dict(os.environ, ZEN_STD=str(ROOT.parent / 'zen/src'))
    env['CFLAGS'] = shlex.join(['-O0', '-Wno-parentheses-equality', '-I' + str(work), '-include', str(work / 'clock_probe.h'), '-I' + str(sdk / 'include'), '-Wl,-rpath,' + str(sdk / 'lib')])
    subprocess.run([str(args.zen.resolve()), 'build', '.'], cwd=work, env=env, check=True, timeout=120)
    env.pop('ZEN_TRACE_PATH', None)
    subprocess.run([str(work / 'check')], env=env, check=True, timeout=15)
    output = work / 'trace.json'
    env['ZEN_TRACE_PATH'] = str(output)
    subprocess.run([str(work / 'check')], env=env, check=True, timeout=15)
    batches = [json.loads(line) for line in output.read_text().splitlines()]
    spans = [span for batch in batches for span in batch['resourceSpans'][0]['scopeSpans'][0]['spans']]
    assert len(spans) == 13
    by_id = {int(s['spanId'], 16): s for s in spans}
    assert len(by_id) == len(spans)
    for ident in range(2, 6):
        assert int(by_id[ident]['parentSpanId'], 16) == 1
    for ident in (6, 11, 16, 21):
        assert by_id[ident]['status']['code'] == 2
    for span in spans:
        assert int(span['endTimeUnixNano']) >= int(span['startTimeUnixNano'])
    assert by_id[1]['status']['code'] == 1
    print('PASS: OTLP numeric parent correlation, phase timings, stale/cancelled roots, disabled zero-clock path')

    env['ZEN_TRACE_PATH'] = str(work / 'batches.ndjson')
    env['ZEN_TRACE_BATCH_TEST'] = '1'
    live = subprocess.run([str(work / 'check')], env=env, check=True, capture_output=True, text=True, timeout=15)
    assert 'Full async batch observed before final flush: true' in live.stdout
    assert 'Partial async batch observed before shutdown: true' in live.stdout
    batches = [json.loads(line) for line in (work / 'batches.ndjson').read_text().splitlines()]
    assert [len(batch['resourceSpans'][0]['scopeSpans'][0]['spans']) for batch in batches] == [32, 3]
    ids = [span['spanId'] for batch in batches for span in batch['resourceSpans'][0]['scopeSpans'][0]['spans']]
    assert len(set(ids)) == 35
    assert '35 accepted, 35 exported, 0 dropped, 0 errors, 2 batches' in live.stdout
    env.pop('ZEN_TRACE_BATCH_TEST')
    env['ZEN_TRACE_PATH'] = str(work / 'missing-directory/failure.ndjson')
    failed_write = subprocess.run([str(work / 'check')], env=env, check=True, capture_output=True, text=True, timeout=15)
    assert '13 accepted, 0 exported, 13 dropped, 1 errors' in failed_write.stdout
    env['ZEN_TRACE_PATH'] = 'x' * 4096
    bad_setup = subprocess.run([str(work / 'check')], env=env, capture_output=True, text=True, timeout=15)
    assert bad_setup.returncode != 0, 'Invalid setup unexpectedly succeeded'
    print('PASS: live async32 batch before shutdown, partial3 live flush, no duplicate export, I/O error stats, invalid setup cleanup')

    if args.app is not None:
        env['ZEN_TRACE_PATH'] = str(work / 'native-early-error.ndjson')
        env['ZEN_PARAKEET_MODEL'] = ''
        early = subprocess.run([str(args.app.resolve()), '--file', str(work / 'missing-document')],
                               env=env, capture_output=True, text=True, timeout=15)
        assert early.returncode != 0, 'Missing document unexpectedly opened'
        assert early.stdout.count('Trace producer:') == 1, early.stdout
        assert early.stdout.count('Trace exporter:') == 1, early.stdout
        print('PASS: native early-error cleanup drains telemetry exactly once')

        if args.render_smoke:
            env['ZEN_TRACE_PATH'] = str(work / 'native-smoke.ndjson')
            smoke = subprocess.run([str(args.app.resolve()), '--smoke'], env=env,
                                   capture_output=True, text=True, timeout=45)
            assert smoke.returncode == 0, smoke.stdout + smoke.stderr
            assert '60 Metal frames' in smoke.stdout, smoke.stdout
            assert smoke.stdout.count('Trace producer:') == 1, smoke.stdout
            assert smoke.stdout.count('Trace exporter:') == 1, smoke.stdout
            print('PASS: native render shutdown drains live telemetry once')
