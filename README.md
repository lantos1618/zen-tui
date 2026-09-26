# Zen TUI

A native macOS voice workspace written in Zen. F2 starts/stops microphone
capture; the app displays a live FFT and measured Metal submission FPS. With a
configured local Parakeet model, stopping a recording transcribes it in a Zen
actor and puts the result in the input box. Enter speaks that text. Escape exits.

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
Microphone. Recording is off at startup and stops after 30 seconds or on F2.
Samples stay local; no cloud transcription endpoint is used.

Only one transcription is admitted at a time. A second recording stopped while
the model is busy is not queued, and the app reports that state. Results use a
bounded 4000-byte UTF-8 reply. Closing during inference waits for the accepted
job to finish and releases the model. No native cancellation API is exposed yet.

By default recordings are memory-only. To save each completed recording as a
mono float32 WAV, set `ZEN_RECORDING_PATH` to an explicit writable path; each
recording replaces that file. This is independent of local transcription.

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
and mailbox lifecycle checks (SDK must be installed).

Validated locally: actual microphone start/activity/stop, 60-frame render smoke,
FFT/WAV numerical checks in zen-audio, and a complete Metal transcription of a
known speech fixture while the window submitted 630 frames. Fresh-install
permission prompting and denied-to-authorized recovery were not UI-tested.

Metal clears/presents frames; Core Animation renders text and bars. FFT is
scalar Zen with a Hann window and 32 linear frequency bands, displayed over a
60 dB amplitude range. FPS counts frame submissions, not GPU completions. This
is not yet a PTY terminal emulator, custom GPU glyph renderer, or SIMD library.
