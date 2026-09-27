# Zen TUI

A native macOS voice workspace written in Zen. F2 starts/stops microphone
capture; the app displays a live FFT and measured Metal submission FPS. With a
configured local Parakeet model, a Zen actor revises the input text while you
record and finishes the latest recording after you stop. Enter speaks that text.
Escape exits.

## Libraries

Keep sibling checkouts under one directory:

- [zen](https://github.com/lantos1618/zen): compiler and standard library.
- [zen-macos](https://github.com/lantos1618/zen-macos): window, native input,
  microphone device, Metal presentation, and speech synthesis.
- [zen-audio](https://github.com/lantos1618/zen-audio): FFT, bands, and WAV encoding.
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
ZEN_STD=../zen/src \
CFLAGS="-I$PWD/../zen-parakeet/build/nemo-speech/include -Wl,-rpath,$PWD/../zen-parakeet/build/nemo-speech/lib" \
../zen/zen build .

ZEN_PARAKEET_MODEL="$PWD/../zen-parakeet/models/parakeet-tdt-0.6b-v3.q8_0.gguf" \
app/ZenTUI.app/Contents/MacOS/ZenTUI
```

The SDK paths are explicit build inputs. The current project builder does not
fetch dependencies or infer include paths. Without `ZEN_PARAKEET_MODEL`, the
window, spectrum, microphone, and speech synthesis work; transcription stays off.
The model is loaded lazily on the first submitted recording and retained by the
worker. Inference uses the native Metal backend (GPU index 0).

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

Stable text is bounded to the most recent 3500 UTF-8 bytes, with an explicit
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
created by default.

## Checks

`--help` does not open a window. `--smoke` renders 60 frames without starting the
microphone or loading the model. The complete fixture test also avoids the mic:

```sh
ZEN_PARAKEET_MODEL=/absolute/path/model.gguf \
ZEN_TRANSCRIBE_WAV=/absolute/path/mono-float32.wav \
app/ZenTUI.app/Contents/MacOS/ZenTUI --voice-smoke
```

It waits at most 1800 event-loop ticks for a nonempty transcript, reports the
text/frame count, and exits. Shutdown still drains accepted inference. Run
`python3 tests/transcription/run.py` for the real-library asynchronous failure
and mailbox lifecycle checks (SDK must be installed). The same tests exercise
live admission, deferred final requests, stale session rejection, 77.5 seconds
of continuous segment/tail accounting, and bounded cumulative display history. Add
`--model ../zen-parakeet/models/parakeet-tdt-0.6b-v3.q8_0.gguf
--wav ../zen-parakeet/build/fixture.wav` to check a real partial and final against
the known quick-brown-fox speech fixture.

Validated locally: 60-frame render smoke, FFT/WAV numerical checks in zen-audio,
a recognizable partial from a four-second fixture prefix, and the full result
from its 8.49-second recording. The updated app also completed the known speech
fixture through Metal while submitting 38 frames. Microphone start/activity/stop
was verified previously; this update used fixtures without restarting the live
user window. Fresh-install permission prompting and denied-to-authorized recovery
were not UI-tested.

Metal clears/presents frames; Core Animation renders text and bars. FFT is
scalar Zen with a Hann window. The voice display has 32 mel bands from 80 Hz to
4 kHz, a −65 to −15 dBFS range, and elapsed-time smoothing with 35 ms attack and
180 ms release. FPS counts frame submissions, not GPU completions. This
is not yet a PTY terminal emulator, custom GPU glyph renderer, or SIMD library.

## Actor messages

The UI sends copied cumulative PCM and model configuration to the inference actor.
The one in-flight request carries a capture session and partial/final identity
on the main-thread handle; these remain attached until its reply is consumed. That
actor sends a typed `deliver(success: bool, text: str)` message to the result
actor; the runtime copies the text before inference scratch storage expires.
The result actor bridges its messages to AppKit's main thread through the
bounded pipe mailbox, polled with a zero timeout and partial-read framing. Neither actor touches window state. A rejected
result-message admission reports an error through the bridge instead of leaving
the UI waiting. Shutdown stops microphone capture, drains inference and result
delivery, then closes
the pipe. A general main-thread actor executor is not implemented yet.

Actors currently run on pthread workers. AppKit and all rendering stay on the
main thread; the input stream, model handle, scratch arenas, and copied message
bytes have separate owners. This bridge is not a lock-free main-thread actor
executor.
