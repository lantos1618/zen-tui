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
