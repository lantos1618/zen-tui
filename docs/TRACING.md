# Local runtime tracing

Launch with `ZEN_TRACE_PATH=/absolute/path/voice.ndjson`. With tracing disabled,
no telemetry workers start and telemetry reads no clocks. PCM, transcripts and
document text are not recorded. Use a fresh destination per run.

Voice requests carry scalar correlation through worker and result actors. The
app records queue delay, execution, result delivery and UI receipt separately.
The exporter copies names, appends batches of 32 off the UI thread, and drains
on shutdown. The UI requests a partial-batch flush and status once per second;
control messages can be refused under pressure and are attempted next interval.
There is no hard delivery or shutdown deadline. A write failure stops further
writes for that exporter and is printed by the status actor during polling.

The application owns telemetry through `run_session` and flushes the live value
after both success and error returns. A deferred closure would capture the
initial record and miss later pending spans. The exporter and stats receiver
are stopped and joined before the allocator owner leaves scope.

Use the sibling `zen-otel` inspector to read the file:

```sh
../zen-otel/build/zen-inspect /absolute/path/voice.ndjson
```

It shows parent/child timing, missing parents and per-operation count, failures,
median, p95, p99 and maximum duration. This is a bounded file inspector, not a
live graphical debugger. Pool metrics require explicit owner-side sampling;
not every application allocation is automatically tracked.

## Build and verification

The current integration requires the actor runtime development compiler and
matching std sources, including `std.trace` and pool snapshots. It has not been
promoted to the main compiler. `tools/build-code.sh` requires an explicit absolute
compiler path and records its hash and repository dirty state. Its inventory
is not a lockfile and a fresh main-branch checkout is not yet sufficient.

```sh
tools/build-code.sh "$PWD/../zen/build/dev/actor-observe-zen"
python3 tests/telemetry/run.py \
  --zen ../zen/build/dev/actor-observe-zen \
  --app app/ZenCode.app/Contents/MacOS/ZenCode
```

The tests verify live full/partial batches, correlation, stale results, errors,
shutdown, disabled worker/clock counts and native early-error cleanup. They do
not load a model or record a microphone. Add `--render-smoke` with `--app` to
open a window for 60 frames and check normal shutdown exactly once. This caught
a deferred-copy cleanup regression. It is not a sustained performance benchmark.
