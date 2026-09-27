# Zen Code library architecture

Zen Code composes independently testable source libraries through `build.zen`.
The app repository keeps its historical zen-tui name. The executable/bundle is
ZenCode / ZenCode.app and the display name is Zen Code.

```mermaid
flowchart TD
  App[Zen Code application] --> Mac[zen-macos]
  App --> DSP[zen-audio]
  App --> Voice[zen-voice]
  Voice --> ASR[zen-parakeet]
  Mac --> Apple[Apple native frameworks]
  ASR --> NeMo[NVIDIA NeMo native runtime]
  App --> Std[Zen standard library]
  Voice --> Std
  DSP --> Std
```

| Owner | Responsibility | Excluded concerns |
|---|---|---|
| zen-macos | Native window/input, Metal presentation, AudioQueue capture, permission display, display scheduling, bundle resources | Speech inference and DSP |
| zen-audio | FFT, speech-frequency display mapping, smoothing, WAV encoding | Devices, windows, actors, models |
| zen-parakeet | Direct native ABI, model/result lifetime, synchronous recognition | UI and microphone policy |
| zen-voice | Copied actor messages, asynchronous recognition, bounded mailbox and live-segment scheduling | Window state, audio device handles, display history |
| Zen Code | Input/display history, model configuration, shortcuts, capture/voice coordination | Compiler/runtime implementation |

The main thread owns AppKit and capture callbacks. A single inference actor owns
its cached native recognizer; a result actor sends copied replies through the
Darwin pipe adapter to the app's event loop. A finalized current-session result
is committed before its exact audio prefix is consumed. Capture continues into
the retained tail. The current bridge is explicitly macOS-specific, even though
zen-voice has no AppKit dependency.

PCM, scratch buffers, and history use caller-owned Zen allocators. Raw capture
pointers are copied into actor messages, not shared with worker threads. UI
history remains in `src/history.zen`, separate from the speech library. The old
`src/transcription.zen` only re-exports compatibility names; it does not maintain
a second implementation.

Native math calls live behind std.math. Apple frameworks and NVIDIA's inference
engine remain external native dependencies; orchestration, capture callbacks,
DSP, actor behaviors, configuration, and library adapters are Zen. No handwritten
C forwarding shim or Python inference process is introduced.

Further separation should follow a second concrete consumer. In particular,
zen-macos still has a convenience App UI; extracting a general UI toolkit before
there is an editor/document model would make an untested abstraction. Full code
editing, undo, projects, PTY integration, and durable transcription are subsequent
milestones, not features claimed by this refactor.

## Remaining work

- File/project model, editing, undo/redo, save and conflict handling.
- Native dependency packaging and signed/notarized distributable builds.
- Capture-to-visible-text latency instrumentation, frame-time graph, and optional
  telemetry export; current timing covers submission intervals only.
- Segment overlap and a backend with native cached streaming support.
- A generic pollable std actor channel. SIMD and compiler optimization work
  should follow measured bottlenecks; typed native handles need a settled design.

Extract a separate UI toolkit when another application establishes reusable
requirements. See [threading](THREADING.md) for current ownership and
[benchmarks](BENCHMARKS.md) for measured limits.
