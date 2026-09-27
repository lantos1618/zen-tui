# Thread ownership and library boundaries

Zen Code keeps AppKit, presentation, capture state, and application text on the
main thread. Parakeet loading and inference run on a Zen actor thread. This is a
source-level ownership audit, not a Thread Sanitizer result.

## Current execution

| Owner | Work and storage |
| --- | --- |
| Main thread | AppKit events, Metal submission, capture controls and PCM storage, FFT, smoothing, history, result polling |
| Inference actor | Cached recognizer, model loading, aligned temporary PCM, synchronous native inference |
| Result actor | Copies typed result messages into the caller's polled pipe |
| Native inference backend | Its own CPU/GPU execution, managed by the native SDK |

`Capture.start` passes the main thread's current CFRunLoop to AudioQueueNewInput.
Audio callbacks and UI access to the recording buffer are serialized on that run
loop. The callback copies samples and re-enqueues a buffer; it does not recognize
speech. Moving it to a background queue requires a synchronized handoff; changing
only its run-loop argument would make the current shared state unsafe.

`Transcriber` admits one outstanding request. Sending copies PCM before returning,
so capture can later modify its storage without racing inference. The worker
copies into float-aligned storage and exclusively owns the recognizer. Result
messages copy text before worker scratch storage is released. The UI polls with
a zero timeout, rejects stale sessions, and consumes only a successfully finalized
current-session prefix.

The actor runtime creates one pthread per actor. Its mailbox limit is 64 queued
messages, but voice admission restricts this pipeline to one request. Sending
still allocates, copies, and acquires runtime locks on the sender: asynchronous
does not mean zero main-thread cost. The library permits a live snapshot of
480,000 float32 samples (1.92 MB); this app caps phrases at 240,000 (960 KB).

## Shutdown

The app closes its native window before waiting for transcription actors.
`App.close` first stops/disposes capture, then releases UI objects. The app
allocator remains alive while the transcriber drains accepted work and joins.
The transcriber is opened first and its cleanup registered before constructing
the app. Reverse defer order closes the app first, then joins the actors. Failed
app construction still drains the transcriber. Each resource has one cleanup;
there is no mutable guard captured by multiple deferred closures.

Native inference is not cancellable. Closing the window does not promise immediate
process termination: model loading or decoding may still delay exit. AudioQueue
stop/dispose is synchronous. Failed disposal retains the queue; capture storage
must remain alive until successful disposal or process exit. The app keeps its
allocator alive through the join but has no disposal-retry recovery UI.

## Remaining limits

- Optional `ZEN_RECORDING_PATH` export encodes and writes WAV synchronously.
  Slow storage can stall UI and capture delivery. A future bounded export actor
  needs owned samples, backpressure, and surfaced completion errors.
- Audio delivery depends on servicing the main run loop. Three 256-sample native
  buffers at 16 kHz provide a small delivery cushion, not a guarantee during UI
  stalls. Measure callback gaps before adding a dedicated audio thread.
- The older-system fallback uses Metal `nextDrawable`, which may wait.
  Display-link mode uses the drawable supplied with the update. Submission
  intervals do not measure actual GPU
  completion or physical presentation. Native inference and drawing also share
  GPU resources despite running on separate CPU threads.
- The result bridge uses Darwin-specific pipe/poll and errno handling. Shutdown
  assumes its one bounded reply fits the pipe. The result actor adds a thread
  and message hop; this is not a work-stealing executor or a portable channel.
- This audit and existing contract tests do not replace live audio stress tests
  or race-detector coverage.

## Library ownership

| Layer | Responsibility |
| --- | --- |
| Zen std | Existing `env.clock` and `Duration`; portable statistics, actor/channel primitives, ownership and runtime improvements |
| zen-macos | Display/run-loop scheduling, AppKit confinement, Metal lifetime, microphone permissions and native audio delivery |
| zen-audio | Portable FFT, bands, smoothing, WAV and measured DSP/SIMD improvements |
| zen-parakeet | Native model ABI, recognizer ownership and backend behavior |
| zen-voice | Bounded admission, session semantics, inference actors and voice-stage measurements |
| Zen Code | History, notices, application composition, export policy and user-visible diagnostics |

Zen Code uses `env.clock.since_start()` for DSP elapsed time and smoke timeouts;
portable elapsed timing does not need a macOS-specific import. Display scheduling
belongs in zen-macos even when its statistics are portable. A generic pollable,
bounded result channel should be designed in std and then used by zen-voice.
SIMD and compiler changes should follow a measured hot path and preserve this split.

`--smoke` requires 60 submitted frames within 30 seconds. `--voice-smoke`
prints submit-to-polled-reply milliseconds using the std monotonic clock. This
includes sender copying, actor delivery, first model load, native inference,
result delivery and UI polling; it excludes audio capture and is not a pure
inference benchmark. Its polling deadline is 30 seconds, but shutdown still
waits for a noncancellable outstanding native call.
