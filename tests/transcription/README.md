# Voice and display-history integration checks

```sh
python3 tests/transcription/run.py
python3 tests/transcription/run.py --model ../zen-parakeet/models/parakeet-tdt-0.6b-v3.q8_0.gguf --wav ../zen-parakeet/build/fixture.wav
```

The runner first invokes the independent `zen-voice/tests/run.py` suite: actual
native model failure, actor admission/poll/close, and optional real CPU speech.
`--wav` must contain the known 16 kHz mono float32 quick-brown-fox fixture from
zen-parakeet. The live test requires recognized words from a four-second prefix
before simulated stop, then expected words from two finalized segments. These
are repeated offline decodes, not native stateful streaming.

The app-owned `continuous_state.zen` imports `voice` and `history` separately.
It simulates 77.5 seconds over five finalized segments plus a stopped tail,
checking exact sample count conservation, busy-stop finalization, stale-session
rejection, cumulative/provisional text, UTF-8-safe bounded history with an
omission marker, and quiet-tail detection. `History` remains application policy;
it is not part of the reusable speech library.

`--zen` selects a compiler and `--sdk` selects the native NeMo SDK. Tests use
temporary headless builds. They never record the microphone or restart an app.
