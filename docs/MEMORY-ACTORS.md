# Memory, allocators, streaming and actors

Assessment: 2026-09-27. Independent read-only sub-agent audit plus focused
verification by the implementation agent. **Not fully allocator-budgeted or
ownership-safe by construction.** Explicit allocation is used widely, but
runtime/native allocation and ownership gaps remain.

## Ownership and memory budget

| Component | Current contract | Assessment |
| --- | --- | --- |
| Capture | 480,000 f32 samples (~1.92 MB), single native run-loop owner | Callback detached before disposal; failed disposal quarantines an inert native token/queue |
| FFT/pitch | Caller-owned scratch; pitch sampled at 10 Hz | Pitch no-allocation guard passes; FFT work now capped at 60 Hz |
| Inference | One in-flight request, copied actor message, aligned worker copy | Bounded request backlog; native model/GPU memory unaccounted |
| WAV export | Candidate runtime: 64 messages and 32 MiB including active payload/overhead | Worker scratch and native allocations are additional |
| Editor | Five fixed document buffers, 64 KiB content limit, one undo | Load/save comparison reads at most capacity+1 bytes, plus path/allocator overhead |
| Actor runtime | malloc per message, pthread per actor | Candidate has 32 MiB message budget; no caller allocator |
| Trace | 4096 app-owned completed-span slots, drops counted | No recording allocation; shutdown JSON uses additional memory |
| UI prototype | Bounded node array; borrowed strings; parent-owned native layers | One-shot renderer; repeated paint appends layers |

## Open findings, in priority order

1. **Compiler integration pending.** The candidate fixes actor size overflow
   and rejects Full/Closed sends before allocation/copy. The regular compiler
   still needs these fixes promoted after aggregate verification prerequisites
   are restored. The app uses the candidate; see below.
2. **Native disposal quarantine.** Failed AudioQueue disposal retains an inert
   token and queue until retry succeeds or the process exits. Fault tests show
   callbacks cannot access the released arena. This trades retention for safe
   lifetime; it does not prove native leak freedom. Capture remains restricted
   to its creating main run-loop thread.
3. **Medium — actor metadata retention.** Joined actor control blocks remain in
   a registry until process exit. Repeated spawn/stop/join retains metadata.
   Reclaim only after defining safe reference/handle lifetime semantics.
4. **Responsiveness — document I/O stays on the UI thread.** Cmd-S reads,
   stages, writes and fsyncs synchronously. Use a bounded file actor with copied
   snapshots and revision acknowledgments; do not overwrite newer edits on ack.

The paused opaque compiler draft is preserved. None of these runtime/compiler
findings has been silently folded into it.

## Changes made following the audit

- `zen-macos` refresh now owns a local autorelease pool. Updates outside tick
  previously left temporary native strings in the app-lifetime pool. Native
  layers retain their assigned strings; temporary objects can drain promptly.
- FFT/band work is limited to 60 Hz even if audio/events wake the UI loop more
  often. Capture polling and 10 Hz pitch remain independent. This bounds
  redundant work; no measured whole-app speedup is claimed for this change.
- Restored `free` forwarding in the native failure-test allocator, required by
  the newer stats implementation. This is test support, not a compiler change.
- Added `zen-audio/tests/pitch/no_alloc.py`, including an injected-allocation
  negative control around the generated pitch function.
- Capture callbacks now use a separately allocated token detached before
  native stop/disposal. Successful disposal frees it; failed disposal blocks
  restart and allows retry without retaining arena state.
- Document load and save comparison use the macOS bounded reader. Oversized
  load reports Capacity; external growth reports Conflict and preserves edits.
  The existing compare/replace race remains.
- Replaced the editor-check Python runner with Node, retaining independent
  positive/failure fixtures. Other Python verification tools remain where
  removing them would weaken coverage.

## Verification

| Check | Result |
| --- | --- |
| Pitch malloc/calloc/realloc guard | PASS; deliberate allocation rejected |
| Native failure-budget lifecycle | PASS: 247 allocation failures, 265 successful repeated closes |
| Capture disposal injection | PASS: failure/retry, restart refusal, late callback after arena release; missing-detach negative control fails |
| Bounded document reads | PASS: 32 MiB sparse input under a 65,537-byte allocation ceiling, exact capacity, growth/conflict, allocation failure and symlinks; unbounded-read negative control fails |
| Editor-check Node runner | PASS: ten controlled positive/failure fixtures; actual extension compile unavailable without npm/dependencies |
| Actor admission | PASS: checked sizes, allocation failures, four producers, active charging, real 1 MiB payload saturation and drain; injected unwanted allocation fails |
| WAV actor snapshot/bounds/drain/atomic replacement | PASS |
| One-hour simulated scheduling and stale/busy/final/error handling | PASS; simulation, not an hour of real speech |
| 77.5-second synthetic segmentation/tail/history accounting | PASS |
| Current app build | PASS |
| Real GPU fixture after integrated safety fixes | PASS: expected transcript, 96 ms warm reply, two exported spans, zero drops, clean exit |
| Frame pacing in fixture smoke | 16 frames, reported 3 FPS / p95 667.93 ms; poor short-run result, not a sustained rendering benchmark |
| SIMD correctness/assembly and prior benchmark | PASS; about 3.3x warm isolated squared-distance speedup |
| ASan/UBSan binary | UNVERIFIED: hangs, including with symbolization/leak detection disabled |
| Native heap/RSS long soak and race detection | NOT RUN |
| Native model/GPU allocation budget | NOT INSTRUMENTED |

Lifecycle counts do not prove native leak freedom or exercise a real
AudioQueueDispose failure. The no-allocation guard covers generated Zen pitch
calls, not every native library allocation or the entire UI loop.

## Where actors help, and where they do not

Inference and export appropriately use actors. Native UI, capture callbacks,
small layout/DSP primitives and UI state belong on their designated owner;
turning every operation into a message would add copying and scheduling cost.
Borrowed result text is copied/consumed before the next poll. Session tags
reject stale replies; successful finalization discards the exact submitted
prefix and preserves the tail.

The current speech backend is offline inference over growing snapshots. Under
an ideal one-second partial cadence through 15 seconds, it revisits 120 seconds
of input duration for 15 seconds of speech (1 + ... + 15), roughly 8x repeated
input work. Actual compute does not scale exactly linearly. Adaptive partial
cadence/VAD or a truly streaming model can beat further small math tuning.

## Recommended next batch

1. Restore aggregate compiler verification prerequisites and promote actor
   admission fixes after verification; investigate the nested union-pattern
   defect exposed by bounded-read tests (explicit dispatch currently avoids it).
2. Define safe actor-handle reclamation and reduce global lock contention
   during message copying without reintroducing shutdown races.
3. Add revision-aware asynchronous document saves.
4. Measure queue delay, inference, copying, allocations and RSS independently;
   run a real audio soak and producer/shutdown stress before declaring compliance.
5. Tune partial cadence against measured word latency and memory, with a
   repeated-word/boundary accuracy corpus before introducing overlap deduplication.

## Actor candidate follow-up

The current app has been rebuilt with `zen/build/dev/actor-zen`. That candidate
fixes findings 2 and 3 for generated sends: checked remaining-capacity sums,
32 MiB per actor including active messages/overhead, and rejection before
allocation/copy. The previous 61/122 MB queue estimates apply to the old runtime;
the new message budget is 32 MiB, excluding worker scratch and native memory.
Four-producer stress, allocation failure, oversized payload and shutdown checks
pass, along with voice and export integration. Global locks during copying are
a known contention tradeoff. The standard compiler binary remains unchanged
until aggregate prerequisites are restored; full ownership compliance is still
not established. Capture-disposal lifetime and bounded document reads are now
fixed and fault-tested, subject to the limitations above.
