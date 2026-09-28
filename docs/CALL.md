# Zen Call local media experiment

A runnable experimental target in zen-tui, using zen-macos. It is separate from
the Zen Code editor executable, so local model/inference setup is not required.

## Run

```sh
ZEN_STD=../zen/src ../zen/build/dev/actor-zen build zen-call
tools/package-call.sh
open build/ZenCall.app
```

Press C once to request/open the camera, F2 to toggle the microphone, and Escape
or the window close button to stop. Closing detaches preview before signaling
and joining the camera worker. The app bundle declares camera/microphone usage.
`--camera` requests the camera on launch; default launch leaves it off.
Camera retry currently requires restarting the app. There is no camera toggle.

## Data flow and ownership

- Camera actor owns session creation, permission waiting, blocking start/stop and
  native lifetime. It publishes one borrowed preview-layer pointer via the local
  pipe. The UI attaches/positions that layer; it detaches before sending EOF to
  the worker and joining it. No frame pointers enter actor messages.
- AudioQueue capture remains on the main run loop through macos.audio.Capture.
  Main sends 320 mono f32 samples (20 ms at 16 kHz; 1,280 bytes) as an owned actor
  message. Only one audio message is in flight. The worker copies into aligned
  samples, computes RMS and acknowledges sequence/byte count/level.
- Main discards the capture prefix only after successful admission. Pending
  capture is trimmed to 6,400 samples (400 ms); dropped samples are displayed.
  The underlying existing capture allocation still holds up to 30 seconds.
- Admission failure or a two-second missing acknowledgment stops/disables
  microphone capture and surfaces a transfer failure. Restart to recover.
- Fixed native pipe replies are smaller than Darwin PIPE_BUF; readers stay open
  through worker join. Camera stop uses EOF, independent of data-pipe capacity.
- Status text uses persistent bounded storage; per-frame formatting storage does
  not escape its arena. Permission polling drops temporary native objects and
  arena allocations each iteration.

This is local transport, not a network call. There is no codec, remote peer,
jitter buffer, synchronized playback, recording or speaker feedback. Camera
frames are managed by AVFoundation's preview pipeline; Zen-owned video frame
buffers and a video actor pipeline are still future work. Apple voice processing
is not enabled on the existing AudioQueue capture. The pitch footer is hidden in this target. FFT bars now analyze actual microphone
samples through zen-audio, and transport status distinguishes microphone off,
waiting for buffers, receiving audio, and transfer failure.

## Checks (2026-09-27)

`ZenCall --smoke` keeps both capture devices off, renders 90 frames, sends one
synthetic 1,280-byte PCM chunk and verifies its byte count and RMS 250/1000.
The sender overwrites its source buffer immediately after enqueue to exercise
actor message ownership. PASS, exit 0; log: build/call-smoke.log.

Live UI verification showed a camera image, microphone authorized/ON, and
604 chunks sent / 603 acknowledged with zero dropped samples. A difference of
one is expected while one message is in flight. This is a point-in-time live
check, not a long soak or latency benchmark. The demo was left open for use.

Remaining: camera error notifications/reconnect, camera stop/restart control,
voice-processed capture, native video-frame delivery, latency distributions,
long-run memory checks, and microphone mute/session transition tests.

## Audio display correction

The original inherited pitch line displayed zeros because this target never ran
pitch estimation. It was not evidence of stopped audio. Zen Call now disables
that line via the native app configuration, connects its FFT bars to zen-audio,
and reports recent actor acknowledgments as receiving audio.

`ZenCall --audio-check` starts local capture for 12 seconds and requires at least
ten acknowledged chunks before exiting. It saves/transmits no media. The live
check passed: startup code 0, 691 frames, 597 chunks sent and acknowledged,
764,160 bytes delivered. Log: build/call-audio-check.log. This verifies buffer
delivery, not microphone quality or pitch accuracy.


## iOS Simulator

From `zen-tui`, run `tools/launch-call-ios.sh`. This builds with the development
actor compiler, packages `build/ios/ZenCall.app`, boots the saved Zen iPhone,
installs the app, and opens Zen Call directly. `package` builds without launching.
Override `ZEN_COMPILER`, `ZEN_STD`, or `ZEN_SIMULATOR_DEVICE` when needed.

The iOS target uses `zen-ui`'s retained UIKit renderer, `zen-ios` audio-session
and bounded AudioQueue capture, and the same `call_audio.AudioWorker` as macOS.
Tap Start microphone to send owned 20 ms PCM messages and display acknowledged
bytes and RMS level. One packet may be in flight; a two-second missing reply
stops capture. Buffered latency is trimmed to 400 ms. Stop and backgrounding
stop capture and deactivate the audio session. Capture does not resume silently.
AudioQueue capture is currently a platform port of the macOS queue implementation;
it has not yet been consolidated into a shared Apple implementation.

Simulator's native camera query returns no device, which the UI reports.
This target does not yet attach an iOS camera preview on physical devices.
There is no network calling, speaker playback, or video fixture playback.
The microphone and camera usage descriptions are included in the app bundle.

Validated on iPhone 17 Pro / iOS 26.2 Simulator: app launch, actual microphone
PCM received by the shared actor (2,144 packets acknowledged), nonzero level,
start/stop control, and stop-on-background with no automatic resume. The macOS
90-frame smoke test also passed after the shared actor extraction.

## Run on a physical iPhone

Open `platforms/ios/ZenCall.xcodeproj` in Xcode. This project runs the Zen
compiler for `arm64-apple-ios17.0` using the iPhoneOS SDK, then lets Xcode
package and sign the result. No Swift/Objective-C implementation is added.
`tools/build-call-device.sh` builds the device executable alone, without signing.

1. Connect and unlock the iPhone; accept Trust This Computer on the phone.
2. Add your Apple Account in Xcode Settings → Apple Accounts.
3. Select ZenCall → Signing & Capabilities → your Team (automatic signing).
4. Select the connected iPhone as the run destination. Enable Developer Mode
   in Settings → Privacy & Security on the phone when required, including reboot.
5. Press Run. Grant microphone permission when starting capture.

A personal Apple Account can be used for local device testing. TestFlight
requires an Apple Developer Program membership and an App Store Connect app.
For TestFlight, complete distribution assets (including the app icon), archive
for Any iOS Device, validate/upload through Organizer, then select the processed
build in App Store Connect TestFlight. External testing may require beta review.
No signing assets or App Store Connect records were created by this setup.

Validation: physical arm64 binary compiled; unsigned Xcode device bundle build
passed. Actual installation is pending a reachable phone and iOS signing assets.
The iOS camera preview remains unimplemented, including on a physical device.

After signing-team setup and device pairing, `tools/run-call-device.sh IPHONE_UDID`
builds with Xcode automatic provisioning, verifies signing, installs, and launches
Zen Call. This command permits Xcode to register the specified device and update
signing assets in the selected Apple Developer team. The phone must be unlocked
with Developer Mode enabled. Missing platform support must be installed through
Xcode Settings → Components first; an older simulator runtime alone may not
satisfy the current Xcode platform package.
