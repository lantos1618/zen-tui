# Background transcription checks

```sh
python3 tests/transcription/run.py
python3 tests/transcription/run.py --model /path/to/model.gguf --wav /path/to/mono-float32.wav
```

`--zen` selects a compiler and `--sdk` selects the installed native NeMo SDK.
The mandatory test uses the actual native library with a missing model file:
it verifies background error delivery, rejection of a second in-flight request,
nonblocking result polling, and idempotent close. The optional fixture performs
real CPU inference using the supplied model and audio. Tests build in temporary
directories; the application runtime does not depend on Python.

`Transcriber` sends actor-owned PCM bytes to a worker that caches its first
successfully loaded model/backend. The UI polls a bounded pipe reply using a
zero timeout and handles partial reads; no filesystem mailbox is used. Reply
text is UTF-8-truncated to 4000 bytes and borrows the handle's buffer until its
next submit/poll. There is one outstanding request per handle. Close waits for
accepted work to finish because the native inference API has no cancellation.
