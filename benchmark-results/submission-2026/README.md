# Benchmark evidence

`submission.json` is the current, schema-valid ADTC participant report. It was
generated from the exact released GGUF after the official Team ID was set and
must be used for self-reporting or comparison with an organizer audit.

The five `codefellow-s045-profiler-*.json` files are immutable pre-submission
model-selection runs. They were produced in a temporary benchmark checkout
before the Team ID was issued, so their `local-codefellow-benchmark`,
`benchmark@example.invalid`, and zero Git SHA values are development labels,
not submission identity. They are retained only to support the disclosed
five-run median and have not been rewritten after measurement.

Other JSON files and subdirectories contain raw model-selection, language,
format, quantization, and matched-comparison evidence. They are not ADTC
participant reports.
