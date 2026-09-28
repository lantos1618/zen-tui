# Zen Code

A native voice workspace with a small single-document editor. The checkout and
GitHub repository are `zen-tui`; the application is Zen Code. Terminal emulation
is not implemented.

[Library architecture](docs/ARCHITECTURE.md) · [Thread ownership](docs/THREADING.md) ·
[Benchmarks](docs/BENCHMARKS.md)

A native macOS voice workspace written in Zen. F2 starts/stops microphone
capture; the app displays a live FFT and measured Metal submission FPS. With a
configured local Parakeet model, a Zen actor revises the input text while you
record and finishes the latest recording after you stop. In voice-workspace mode,
Enter speaks that text and Escape exits. Document mode has separate editing controls.

## Libraries

Keep sibling checkouts under one directory:

- [zen](https://github.com/lantos1618/zen): compiler and standard library.
- [zen-macos](https://github.com/lantos1618/zen-macos): window, native input,
  microphone device, Metal presentation, and speech synthesis.
- [zen-audio](https://github.com/lantos1618/zen-audio): FFT, bands, and WAV encoding.
- [zen-voice](https://github.com/lantos1618/zen-voice): actor-based transcription,
  bounded messages, and continuous dictation scheduling.
- [zen-parakeet](https://github.com/lantos1618/zen-parakeet): direct native NeMo
  Speech C bindings and resource ownership for Parakeet v3.

The app owns the workflow. DSP and inference do not live in the macOS SDK. All
application, FFT, adapter, and actor code is Zen. Apple frameworks and NVIDIA's
C++ inference runtime are external native dependencies; there is no Python
inference process or handwritten C forwarding shim.

## Build and run

Requires Apple silicon, macOS 13+, Apple's command-line developer tools, the
current Zen compiler, and NVIDIA's native SDK. First follow zen-parakeet's
README to install the pinned SDK into `zen-parakeet/build/nemo-speech` and the
verified model into `zen-parakeet/models`. These downloads are excluded from Git.

From this repository:

```sh
tools/build-code.sh "$PWD/../zen/build/dev/actor-observe-zen"

app/ZenCode.app/Contents/MacOS/ZenCode --set-model \
  "$PWD/../zen-parakeet/models/parakeet-tdt-0.6b-v3.q8_0.gguf"
app/ZenCode.app/Contents/MacOS/ZenCode --check-config
open app/ZenCode.app
```

The current telemetry integration requires the `actor-observe-zen` development
compiler and matching sibling std sources. The regular compiler has not yet
been promoted; a fresh clone alone does not reproduce this development setup.
The build script requires an explicit absolute compiler path and records its
hash, repository revisions and dirty state in `build/code-build-inputs.txt`.
That inventory exposes local dependencies; it is not a dependency lockfile.

The SDK paths are explicit build inputs. The current project builder does not
fetch dependencies or infer include paths. Configure the local model once with
`--set-model /absolute/model.gguf`; the app stores only its path
in `~/Library/Application Support/dev.zen.code/model-path.txt`. Normal Finder launches then work
without shell configuration. `ZEN_PARAKEET_MODEL` overrides that saved path;
an empty override intentionally disables transcription. `--check-config` verifies
that the selected file exists without opening a window or loading the model.
Invalid configuration commands leave the previous selection intact. No weights
are copied or downloaded. Moving the model requires configuring its new path.
Configuration does not modify the signed bundle. Existing development bundles
still read their legacy `Contents/Resources/model-path.txt` when no user setting
exists; `--set-model` writes the new user setting.
Without either setting, the window, spectrum, microphone, and speech synthesis
work; transcription stays off.
With a model configured, startup loads it and decodes one second of synthetic
silence on the inference actor. F2 capture is enabled after the ready reply;
warm-up never uses the microphone. The worker retains the model, using the native
Metal backend (GPU index 0). Preparation can still contend with rendering.

## Voice and permissions

Press **F2** (or Fn-F2 if your keyboard uses media keys). macOS controls microphone
authorization. The app declares its purpose and shows authorization/status;
if access is denied, enable it in System Settings > Privacy & Security >
Microphone. Recording is off at startup. With a model configured, F2 starts
continuous dictation and stops it on the next press; successful segments free
space in the bounded capture buffer. Without a model, capture retains its
30-second automatic limit. Samples stay local; no cloud endpoint is used.

The current Parakeet TDT v3 encoder supports offline decoding, not the native
streaming API. Live partials therefore decode growing, cumulative audio prefixes
using the cached model. When the worker is idle and at least one more second of
16 kHz audio is available, the app submits the latest prefix. Words can change
as later context arrives, and short prefixes may return no text; this is not a
stateful streaming decoder or a guaranteed one-second display latency.

Only one inference is in flight. Partial requests use a growing prefix of the
current segment; old intermediate requests are never queued. After eight seconds,
a quiet 300 ms tail permits a phrase boundary. Fifteen seconds is the hard segment
limit. Successful finalized text is appended to the stable history, and only its
exact submitted audio prefix is removed. Audio arriving during inference remains
as the next segment's tail. No overlap is used yet: a forced boundary in continuous
speech can reduce word accuracy around that boundary.

The capture buffer still holds at most 30 seconds. This leaves headroom while a
segment decodes; if inference falls behind enough to exhaust it, capture stops
with an explicit overflow notice instead of silently overwriting audio. Model
failure also stops capture and retains the uncommitted prefix. Stop retains a
final request for any tail, even when an earlier partial or segment is busy.
Starting a new capture supersedes the previous session; late replies cannot
modify its text or discard its audio.

In voice-workspace mode, stable text is bounded to the most recent 3500 UTF-8 bytes, with an explicit
`[Earlier text omitted]` marker after trimming. The window shows approximately
the latest 600 bytes so new words stay visible; speech uses the retained full
input buffer. This is a rolling display, not a durable unlimited transcript.
Native replies are capped at 4000 UTF-8 bytes. Closing waits for accepted inference
to finish and releases the model; native cancellation is not exposed.

By default recordings are memory-only. To save each completed recording as a
mono float32 WAV, set `ZEN_RECORDING_PATH` to an explicit writable path. During
continuous dictation each successfully completed segment replaces that file;
it does not contain the entire session. With transcription disabled, stopping
the bounded recording saves the whole retained recording. No audio file is
created by default. Encoding and atomic file publication run in a separate export
actor. Admission copies the PCM before the capture buffer is reused; each request
is capped at 480,000 samples. The app built with `zen/build/dev/actor-zen`
limits each actor to 64 queued-or-executing messages and 32 MiB including
message overhead; working buffers/native allocations are additional. The
regular compiler has not yet been promoted and still uses the old count-only
limit (up to 122.9 MB queued PCM).
Accepted exports drain on shutdown, so slow storage can delay exit. Queue
admission failures are reported by the app; encoding and filesystem failures are
logged to the console. This optional export is not a durable full-session archive.

## Editing a document

Launch an existing UTF-8 file explicitly:

```sh
app/ZenCode.app/Contents/MacOS/ZenCode --file /absolute/path/example.zen
```

Arrow keys move the cursor; typing, Tab, Enter and Backspace edit the document.
Cmd-Z undoes one edit, and Cmd-S saves. F2 dictation previews partial text at the
cursor and inserts each finalized phrase as one undoable edit. The document is
limited to 64 KiB of UTF-8; cursor movement follows Unicode scalar boundaries,
not grapheme clusters. The view shows a bounded region around the cursor.

An ordinary close request with unsaved changes keeps the window open. Save first,
or use Cmd-Shift-Q to discard and close. There is no autosave or crash recovery.
Saving compares the file against its loaded/saved baseline and refuses detected
external changes before atomic replacement. A concurrent writer can still race
between that check and publication. Save failure retains the in-memory edits;
saving is currently synchronous on the main thread.

This is a minimal editor: no selection, clipboard/IME integration, redo,
multi-document UI or project browser. Run `python3 tests/document/run.py` for
UTF-8 edits, bounds, undo and file-conflict checks, and
`python3 tests/export/run.py` for copied PCM, bounded admission, drain and atomic
recording export.

## Checks

`--help` does not open a window. `--smoke` renders 60 frames without starting the
microphone or loading the model. The complete fixture test also avoids the mic:

```sh
ZEN_PARAKEET_MODEL=/absolute/path/model.gguf \
ZEN_TRANSCRIBE_WAV=/absolute/path/mono-float32.wav \
app/ZenCode.app/Contents/MacOS/ZenCode --voice-smoke
```

It prepares the model before submitting the fixture. The overall polling limit
is 30 seconds, including preparation. It reports text, frame count, and warm
submit-to-reply time; the reported interval excludes preparation and capture.
Shutdown still drains accepted inference,
so an outstanding native call can delay process exit beyond that deadline. Run
`python3 tests/transcription/run.py` for the real-library asynchronous failure
and mailbox lifecycle checks (SDK must be installed). The same tests exercise
live admission, deferred final requests, stale session rejection, 77.5 seconds
of continuous segment/tail accounting, and bounded cumulative display history. Add
`--model ../zen-parakeet/models/parakeet-tdt-0.6b-v3.q8_0.gguf
--wav ../zen-parakeet/build/fixture.wav` to check a real partial and final against
the known quick-brown-fox speech fixture.

See [performance measurements](docs/BENCHMARKS.md) for smoke results and
remaining pacing limits. Fresh-install permission prompting and
denied-to-authorized recovery have not been UI-tested.

Metal clears/presents frames; Core Animation renders text and bars. FFT is
scalar Zen with a Hann window. The voice display has 32 mel bands from 80 Hz to
4 kHz, a −65 to −15 dBFS range, and elapsed-time smoothing with 35 ms attack and
180 ms release. FPS counts frame submissions, not GPU completions. This
is not yet a PTY terminal emulator, custom GPU glyph renderer, or SIMD library.

## Actor messages

`zen-voice` owns inference and bounded copied replies. The app owns rolling
history and rejects results from superseded capture sessions. UI and capture
stay on the main thread; neither speech actor touches window state. See
[thread ownership](docs/THREADING.md) for copying, mailbox, shutdown, and remaining
main-thread costs, and [zen-voice](https://github.com/lantos1618/zen-voice) for the
public pipeline API.

## Packaging

Zen Code uses bundle identifier `dev.zen.code`. The Zen packaging target copies
an existing build into a separate bundle and discovers its transitive native
libraries using Apple's `otool`. It copies the needed SDK dylibs, rewrites their
load paths to bundle-relative locations, removes build rpaths, includes the
SDK's license notices, and applies an ad-hoc development signature. The input
bundle and SDK remain untouched. No compiler or SDK checkout is needed to run
the resulting bundle; a separately installed model is still required for voice
transcription.

```sh
ZEN_STD=../zen/src ../zen/zen build zen-package
build/zen-package app/ZenCode.app ../zen-parakeet/build/nemo-speech \
  build/package/ZenCode.app
build/package/ZenCode.app/Contents/MacOS/ZenCode --set-model /absolute/model.gguf
open build/package/ZenCode.app
```

The output path must not already exist. Use a fresh destination for each build;
a failed operation may leave an incomplete output. Packaging deliberately omits
saved developer model paths and discovers dependencies only in the supplied
SDK's flat `lib` directory. Unknown non-system dependency paths fail explicitly.
The packager is Zen using `std.proc` argument vectors; it does not invoke a shell
or introduce native forwarding shims.

Run `python3 tests/packaging/run.py` after building both targets. It relocates the
bundle to a temporary path containing spaces, checks dependency paths and code
signatures, exercises user configuration with an isolated home directory, and
proves a missing bundled library cannot silently fall back to the SDK. On hosts
that permit applying a local sandbox, add `--deny-sdk` to verify launching with
all reads of the original SDK explicitly denied. These checks are headless and
do not access the microphone or load model weights.

Ad-hoc signing is for local development; this is not Developer ID signing or
notarization, and does not establish Gatekeeper acceptance or compatibility on a
fresh Mac. Only the local Apple-silicon host has been tested. Native SDK/model
redistribution terms still apply; model weights are not bundled or downloaded.

The voice overlay shows the mean, lowest and highest accepted speaking pitch
from the last three seconds (Hz). Silence is excluded and old readings expire.
Deep (<130 Hz), mid (130–199 Hz) and high (200+ Hz) are descriptive app bands,
not gender classifications or measured full vocal range. DSP lives in
`zen-audio`; Zen Code samples it at 10 Hz and `zen-macos` displays the result.

## Optional local traces

Set `ZEN_TRACE_PATH=/absolute/path/voice-trace.ndjson` before launch. The opt-in
exporter actor writes an OTLP JSON document every 32 completed spans; orderly
exit drains a final partial batch. Output is append-only NDJSON, so use a fresh
filename per run. Encoding and file I/O happen on the exporter worker, not the
UI or capture callback. The file itself is not size-limited or rotated.

Each model-preparation/transcription request has a correlated root and child
spans for actor admission/queueing, worker execution, result delivery and UI
receipt. Execution includes model load/copy/decode; result timing includes its
actor queue and header preparation. Superseded, cancelled and unfinished requests
are marked failed; stale IDs cannot complete a newer span. No transcript or audio
payload is captured. Disabled telemetry allocates no span storage, starts no
workers and reads no clocks (verified with native instrumentation).

The exporter has bounded batching/mailbox storage. A full mailbox drops that
telemetry submission without retrying on the UI thread. Final console counters
report producer rejections and worker accepted/exported/dropped/error totals.
A successful enqueue is not proof of export; file writes can fail or block,
including during shutdown. A bounded 4,096-span inspection snapshot remains
available separately; its contents are never exported a second time.

See `../zen-otel/docs/EXPORTER.md` for limits and append/error semantics.
Run `python3 tests/telemetry/run.py --zen ../zen/build/dev/actor-observe-zen` for
synthetic correlation/OTLP/disabled-path/live-batch checks; no microphone or model
is needed.

See [the memory and actor audit](docs/MEMORY-ACTORS.md) for verified ownership
contracts, current memory-budget gaps, focused checks and prioritized fixes.

## Local call-style media experiment

`zen-call` builds `build/ZenCall.app`: local camera preview plus bounded PCM
transfer to a Zen actor. Run `tools/package-call.sh` after building; C starts
the camera, F2 toggles microphone capture, and Escape closes. No networking,
recording or speaker playback. See [the media experiment](docs/CALL.md) for
build commands, ownership, live verification and remaining work.

### Launch Zen Call on iOS Simulator

Run `tools/launch-call-ios.sh` to build, install, and open the native iOS media
experiment directly. Microphone PCM goes through the shared Zen audio actor.
Simulator reports no camera; physical-device video integration is pending.
See [Call details](docs/CALL.md).

Low-volume tracing requests a partial-batch flush and status once per second
while the UI runs. These control messages are best-effort under mailbox pressure;
final drain still runs at shutdown. File-write errors are printed during the run.
