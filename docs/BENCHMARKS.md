# Zen Code performance baseline

Measured 2026-09-27 on Apple M2 Pro, 12 cores, 16 GiB, macOS 26.6.2.
App and benchmark C code use optimized builds. The actual Zen compiler SHA-256
is `5688b03fceaf54fa1a9cb675c25260e1402c47247e9996ba7c51122aa676a285`.
Background user applications remained running; benchmark workloads were sequenced.

## DSP and capture memory operations

| Workload | Median | p95 of batch means |
|---|---:|---:|
| FFT1024 + 32 voice bands + smoothing | 16.018 µs | 17.340 µs |
| Append256 + consume256, retaining 10s/640KB | 15.444 µs | 16.240 µs |

Each uses 93 timed batch means of 1000 iterations, over three processes, after
warmup. These p95s are not individual-call latency percentiles. The capture case
intentionally shifts 640 KB on every iteration; the real app consumes a segment
much less frequently. Neither benchmark activates the microphone. FFT processing
is about 0.096% of a reference 16.67 ms frame budget; this is not a measured FPS.

Sources and reproduction:
[zen-audio results](https://github.com/lantos1618/zen-audio/blob/main/benchmarks/RESULTS.md),
[zen-macos results](https://github.com/lantos1618/zen-macos/blob/main/benchmarks/RESULTS.md).

## Native speech inference

| Audio duration | CPU median | Metal median | Metal p95 |
|---|---:|---:|---:|
| 1 second | 78.319 ms | 38.324 ms | 39.679 ms |
| 4 seconds | 244.167 ms | 83.213 ms | 97.796 ms |
| 8 seconds | 405.589 ms | 144.436 ms | 147.619 ms |
| 15 seconds | 619.680 ms | 233.275 ms | 234.993 ms |

One cached Parakeet TDT v3 Q8 recognizer per backend, one excluded primer per
length, five measured calls. With five samples, nearest-rank p95 is the maximum.
The synthetic known-speech fixture was repeated with silent gaps and truncated
to each duration; results were nonempty and expected phrase words were checked.
This measures execution, not speech-recognition accuracy. Full configuration,
hashes, raw observations, startup and memory are in the
[zen-parakeet report](https://github.com/lantos1618/zen-parakeet/blob/main/benchmarks/RESULTS.md).

The first CPU process spent 10.014 seconds opening the model, including 9.901
seconds of SDK Metal-library initialization before CPU selection. The later
Metal process opened in 83 ms with warmer caches. That is not a controlled
CPU/GPU cold-load comparison. First eight-second inference took 778 ms CPU /
569 ms Metal. Whole-process maximum RSS was approximately 850 / 820 MiB;
these figures include fixtures and runtime state, not just model weights.

## What this establishes

Warm native recognition is faster than real time on these fixtures. DSP is a
small fraction of the frame budget; these measurements do not justify adding
SIMD complexity to the visualization now. Startup/library initialization deserves
attention before optimizing an already-small FFT workload.

The app still waits for audio to accumulate and revises offline hypotheses.
These benchmarks exclude microphone delivery, actor transport, poll delay,
rendering, and user-perceived word latency. They do not establish one-second
end-to-end latency or performance on another machine. Next measurements should
instrument capture-to-partial latency and cold-start state presentation. A true
cache-aware streaming backend remains a separate capability, not a speed claim
about this offline model.

## Display-link integration check

The display-link integration adds submission interval p95/p99 over the latest
240 intervals, refreshed at most twice per second. These are individual
submission intervals, unlike the batch-mean DSP percentiles above. They do not
measure GPU execution or physical presentation, and initial samples include
startup. `--smoke` now requires 60 submitted frames within 30 seconds.

A local fixture run during integration transcribed “the quick brown fox jumps
over the lazy dog” while submitting 36 frames. Submit-to-polled-reply was 632 ms,
including model load, actor transport and UI polling. This is one smoke
observation with warm system caches, not a latency distribution or microphone
end-to-end benchmark. The final validation record should be used for any later
measurements after code changes.

Visual inspection of the rebuilt app showed both status rows without clipping.
A visible idle snapshot reported 60.1 submission FPS, p95 16.91 ms and p99
17.19 ms. A brief microphone/FFT check reported 60 FPS, p95 17.05 ms and p99
17.84 ms, with received audio and error code zero; capture was then stopped.
These snapshots are not a sustained-performance guarantee. Separate long SDK
runs slowed markedly and missed their frame-count deadline, without inference
running; the cause remains unclassified. See the SDK README for those results.
A bounded Metal System Trace was saved locally under the SDK's ignored build
folder; raw system traces are not published with source.

Final rebuilt-app checks (exit zero, display link active in both):

| Check | Submitted frames | Last FPS window | p95 / p99 interval | Submit-to-reply |
| --- | ---: | ---: | ---: | ---: |
| Render smoke | 60 | 58.1 | 16.77 / 33.41 ms | n/a |
| First fixture transcription | 31 | 27.1 | 33.32 / 33.32 ms | 617 ms |

The fixture text matched the known phrase. This short first-inference run
includes startup and native GPU pipeline initialization; the lower submission
rate is a remaining performance observation, not evidence that CPU actors are
serializing inference onto the UI thread. Separate warm-inference and
presentation traces are needed before assigning a cause or promising 60 FPS
under transcription load.

### Trace correlation

The bounded SDK Metal trace records the test process as foreground from
1.269–2.839 seconds, then background through the end at 11.089 seconds.
Submissions fall from 42 in the partial first second and 50 in the transition
second to roughly three per second afterward. Its GPU clear intervals were
about 19.4 µs median, 22.1 µs p95 and 23.9 µs maximum; CPU-to-GPU latency was
about 0.589 ms median, 0.966 ms p95 and 1.933 ms maximum. No drawable-buffer-wait
rows were recorded.

This correlates the traced slowdown with background state and rules against
heavy GPU clear work in that trace. It does not establish the cause of every
prior long-test failure, measure Core Animation text/compositor cost, or explain
the separate first-inference dip. The trace ended at the recording time limit;
xctrace reported a backdated-signpost warning and saved a readable trace.
