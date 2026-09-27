# Thread ownership and library boundaries

Zen Code keeps AppKit, presentation, capture state, and documents on the main
thread. Model preparation, inference, and optional recording export run on Zen
actor threads. This is a source-level ownership audit, not a Thread Sanitizer
result.

## Current execution

| Owner | Work and storage |
| --- | --- |
| Main thread | AppKit events, Metal submission, capture controls and PCM storage, FFT, smoothing, documents/history, result polling, explicit document saves |
| Inference actor | Cached recognizer, model loading and warm-up, aligned temporary PCM, synchronous native inference |
| Result actor | Copies typed preparation/transcription replies into the caller's polled pipe |
| Optional export actor | Copied recording segments, aligned temporary PCM, WAV encoding and atomic file publication |
| Native inference backend | Its own CPU/GPU execution, managed by the native SDK |

`Capture.start` passes the main thread's current CFRunLoop to AudioQueueNewInput.
Audio callbacks and UI access to recording storage are serialized on that run
loop. The callback copies samples and re-enqueues a buffer; it does not recognize
speech. Moving it to a background queue requires a synchronized handoff; changing
only its run-loop argument would make the current shared state unsafe.

With a configured model, the app submits preparation after opening the window.
The inference actor loads the model and decodes one second of synthetic silence;
its tagged reply enables F2 capture on success. No microphone audio is collected
for warm-up. This separates startup from dictation readiness but does not remove
GPU contention or guarantee smooth frames during preparation. The worker retains
one model/backend identity and refuses requests that attempt to change it.

`Transcriber` admits one outstanding request, including preparation. Sending
copies PCM before returning, so capture can later modify its storage without
racing inference. The worker copies into float-aligned storage and exclusively
owns the recognizer. Results copy text before worker scratch storage is released.
The UI polls with a zero timeout, rejects stale capture sessions, and commits a
successful final transcript before consuming its exact audio prefix. Document
mode inserts finalized text at the current cursor; partials are previews only.

The runtime creates one pthread per actor and limits each mailbox to 64 pending
messages. Voice admission narrows its pipeline to one request. Sending still
allocates, copies, and acquires runtime locks on the sender. The library permits
480,000 float32 samples (1.92 MB); this app caps inference phrases at 240,000
samples (960 KB).

`ZEN_RECORDING_PATH` creates a separate export actor. Admission copies the path
and PCM before capture storage is discarded. Requests are capped at 480,000
samples, with up to 64 pending messages: at most 122.9 MB of queued PCM, plus
message overhead and working buffers. Each export uses a temporary arena for
aligned audio, WAV encoding, and same-directory atomic publication. Queue
admission failures produce an app notice; encoding and filesystem failures log
to the console. There is no export-completion reply or retry queue. Dictation may
continue after export refusal; this is optional segment export, not a durable
full-session recording.

## Shutdown

The native app closes first, stopping capture before releasing UI objects. The
optional export actor then drains and joins, followed by the transcription actors.
The app allocator remains alive through these joins. Cleanup is registered in
reverse dependency order, so failed app construction also releases already-open
actors. Editor mode intercepts ordinary close requests while there are unsaved
changes; explicit discard closes without saving.

Native inference is not cancellable. Model preparation, decoding, or slow export
storage can delay process exit after the window closes. AudioQueue stop/dispose
is synchronous. Failed disposal retains the queue; capture storage must remain
alive until successful disposal or process exit. There is no disposal-retry UI.

## Remaining limits

- Admission still copies PCM on the main thread. Document saves synchronously
  read and atomically publish files there too; fsync or slow storage can delay
  capture delivery even with a 64 KiB document limit.
- Audio delivery depends on servicing the main run loop. Three 256-sample native
  buffers at 16 kHz provide a small cushion, not a guarantee during UI stalls.
  Measure callback gaps before adding a dedicated audio thread.
- The older-system fallback uses Metal `nextDrawable`, which may wait.
  Display-link mode uses the drawable supplied with the update. Submission
  intervals do not measure GPU completion or physical presentation. Inference
  and drawing share GPU resources despite separate CPU threads.
- The result bridge uses Darwin-specific pipe/poll and errno handling. Shutdown
  assumes its one bounded reply fits the pipe. The result actor adds a thread
  and message hop; this is not a work-stealing executor or a portable channel.
- Finalized speech segments have no overlap. Growing-prefix decoding is not a
  backend with native streaming state. Scheduler simulations are not proof of
  hour-long live recognition accuracy or real-time audio reliability.
- Contract tests do not replace sustained live audio tests or race detectors.

## Library ownership

| Layer | Responsibility |
| --- | --- |
| Zen std | `env.clock`, `Duration`, portable statistics, actor/channel primitives, ownership and runtime improvements |
| zen-macos | Display/run-loop scheduling, native events, Metal lifetime, permissions, audio delivery and native atomic file publication |
| zen-audio | Portable FFT, bands, smoothing, WAV and measured DSP/SIMD improvements |
| zen-parakeet | Native model ABI, recognizer ownership and backend behavior |
| zen-voice | Preparation/inference actors, bounded admission and capture-session semantics |
| Zen Code | Documents, history, configuration, export policy, packaging and user-visible diagnostics |

Zen Code uses `env.clock.since_start()` for DSP elapsed time and smoke timeouts.
Display scheduling belongs in zen-macos even when its statistics are portable.
A generic pollable bounded result channel should be designed in std and then
used by zen-voice; compiler/SIMD work should follow measured bottlenecks.

`--smoke` requires 60 submitted frames within 30 seconds without loading a model.
`--voice-smoke` prepares the model before submitting its fixture, then reports
warm submit-to-polled-reply time. That interval includes sender copying, actor
transport, inference, result delivery and UI polling; it excludes preparation
and capture. The overall polling deadline includes preparation and is 30 seconds.
Shutdown still drains any noncancellable native call beyond that deadline.
