# Zen Code foundation plan

Requested 2026-09-27. Execute this foundation milestone in the existing app
repository, preserving its history and the paused opaque compiler draft.
The app is named Zen Code; the GitHub repository remains zen-tui for now.

## Deliverables and acceptance checks

1. Extract `zen-voice`: actor-owned Parakeet model, copied messages, bounded
   replies, continuous-segment admission. No AppKit, Metal, or UI history.
   Existing actor/model/state tests must work through the public library.
2. Rename the app/bundle and build output to Zen Code. Keep the real app on
   zen-macos. Move text history into the app. Provide a Zen configuration command to persist a local model path in the
   bundle's ignored resources so Finder launch does not silently disable voice.
   Environment override remains supported; no model download at launch.
3. Add reproducible Zen benchmarks: FFT/voice bands/smoothing, capture buffer
   consumption, and Parakeet cold/warm CPU+Metal inference at multiple lengths.
   Record build flags, machine, SDK/model identity, raw ignored results, and
   median/p95/real-time factor. Do not infer hardware-independent guarantees.
4. Build the app, run focused actor/audio/history regressions and fixture/render
   smoke checks, publish measured results and library ownership documentation,
   and commit/push completed repositories. Do not interrupt an existing session.

## Library boundaries

- zen/std: language/runtime, memory, scalar math, collections, actors, build.
- zen-macos: AppKit/Metal presentation, audio capture, permissions, bundle paths.
- zen-audio: platform-independent PCM/FFT/voice visualization/WAV operations.
- zen-parakeet: native inference ABI, recognizer lifecycle, WAV fixture support.
- zen-voice: asynchronous speech pipeline and bounded dictation segmentation.
- Zen Code: user interaction, display history, configuration, composition.

Native Apple/NVIDIA dependencies stay explicit. Portable DSP does not import
macOS. The current actor-to-UI bridge is Darwin POSIX, not a portable executor.

## Subsequent milestones (not claimed implemented)

- File/project model, document editing, undo/redo, save and conflict handling.
- Separate UI toolkit if a second app establishes reusable rendering needs.
- Cached streaming ASR backend and segment overlap after measured evidence.
- General main-thread actor executor; native typed handles once opaque design
  is settled. SIMD only after benchmarks identify a worthwhile bottleneck.
- Packaging native SDK dependencies and signed/notarized distributable builds.

## Execution record

Completed locally:

- Reusable zen-voice library extracted; app History remains separate.
- Zen Code 0.2 bundle built; --set-model/--check-config verified from another
  working directory without the environment override. Invalid paths preserve
  existing configuration.
- Native error/lifecycle and real-model partial/two-segment library tests passed.
  App state/history tests cover 77.5 seconds with UTF-8 bounds and exact tails.
- Zen Code loaded its saved model and transcribed the known fixture through
  Metal while submitting 633 frames, without microphone access.
- Benchmarks executed with the same compiler as the app; see BENCHMARKS.md.
- Paused opaque compiler draft preserved, no compiler/seed changes included.

Publication: with explicit approval, zen-voice commit 3295d07 is published at
https://github.com/lantos1618/zen-voice. Existing public library updates are
published. Zen Code's dependency migration is commit 3092b5d in zen-tui.
