# Conditional certificates for periodic loops with deferred faults

A self-contained research artifact for a restricted loop language with deferred
faults: structural certificate checking, sequential and event-driven
interpreters, finite oracles, certified exports, fixed-skeleton annotation
optimization, and handwritten proofs. It is not a production compiler or a
proof-assistant development.

## Setup and quick checks

Python 3.10 or later and the standard library are sufficient. No installation,
network, external solver, private data, GPU, or sibling paper directory is needed.
Run these portable checks from this repository's root:

```sh
python -B -m unittest discover -s tests -v
python -B -m semantic_certificates cases/guarded-division.json
python -B verify_frontiers.py
python -B verify_replay.py
```

The unit suite currently contains 56 methods. The `verify_*.py` commands
reconcile retained results; they do not rerun the experiments. Reconciliation
refreshes the corresponding summary JSON files, so use a separate extraction
when preserving the supplied measurements.

## Full reproduction

The bounded driver requires a POSIX system with Python's `resource` module and
at least 4 GiB available to the process group:

```sh
python reproduce.py
```

To reconcile the original stored counts without rerunning that campaign, use
`python -B verify_results.py` on POSIX as well; its summary dependency imports
the POSIX `resource` module. The frontier/replay reconcilers above are portable.

It runs all 44 steps serially, pins each child to one available CPU, applies a
3.5 GiB address-space ceiling and 40-second soft / 44-second hard CPU limits,
and stops on a nonzero exit or an 80-second child wall timeout. A slow machine
may hit these limits; do not lower coverage and call that a full reproduction.
The driver refreshes results, logs, and generated cases in place. Use a fresh
extraction for a new run.

The recorded memory interpretation is Linux-specific (`ru_maxrss` in KiB).
Affinity and address-space limits do not disable swap: use a no-swap host or a
process cgroup with zero swap allowance. The scientific-checks workflow provides
a pinned Python 3.12.14 container, one CPU, 4 GiB memory, zero process swap, and
checks the effective cgroup limits before running.

For bounded batches, the first command starts fresh and subsequent commands
resume its completed prefix:

```sh
python reproduce.py --max-steps 1
python reproduce.py --resume --max-steps 1
# Repeat the resume command until all 44 steps are recorded.
```

Resume only on unchanged extracted files; `--resume` does not verify source
identity. After any code modification, re-extract and start again. For a single
diagnostic stage, use `python reproduce.py --step tests` (or another stage named
in `reproduce.py:STEPS`). A diagnostic stage is not a complete campaign.

`results/reproduction.json` lists requested/completed steps, exits, timeouts and
resource measurements. A complete successful sequence is required for
`all_steps_passed`. Scientific reconciliation compares counts and invariants,
not timing equality or machine fingerprints. No third-party system is rerun.

## Certificate and execution inputs

`cases/` contains executable JSON examples, including generated sources,
admitted certificates, rejected construction candidates, and counterexamples.
The fixed generated seed is 72913; all 96 generated schemas have 24 retained
inputs with trip counts 0–12 and integer inputs from -3 through 3.

A certificate declares source nodes, actual/predicted Boolean atoms, input and
guard releases, costs/resources, initiation interval, attempts, and retirement.
Optional exports carry checked same-source value-or-fault tickets.
`proofs/semantics.md` and `proofs/frontiers.md` define the model;
`semantic_certificates/checker.py` implements admission and representation caps.
The CLI rejects duplicate JSON keys and files above 4 MiB. Availability maps
must have exactly the declared keys and strict integer releases (Booleans are
not integers for this purpose).

To compare executions of an admitted certificate, add `--input path.json`.
Execution input is an object with nonnegative integer `n`, length-`n` Boolean
lists under `guards`, length-`n` value lists under `inputs`, and
`initial[node][negative_index_as_string]` for reached negative source indices.
Inputs are values, never fault tokens. JSON arrays become functional tuples.
The execution API assumes these well-formed finite inputs; it is not a hostile
file sandbox. The certificate CLI exits 0 for acceptance/equal executions and
2 for rejection or a handled input error.

## Export synthesis and optimum replay

`semantic_certificates.frontiers` exposes `selection_at`,
`earliest_selection`, `obstruction_at`/`verify_obstruction`, `hybrid_at`,
and `hybrid_design_space`. The design-space search reports truncation when
retirement exceeds the maximum representable period, 256.
`proofs/frontiers.md` gives the premises and finite cutoff;
`proofs/frontier-protocol.md` records domains, denominators and failure rules.

`optimization_witness.certify_budget` produces an optimum witness.
`optimization_replay.verify_optimum` checks it against an externally supplied
fixed skeleton and budget. For separate JSON objects:

```sh
python -m semantic_certificates.optimization_replay skeleton.json proof.json --budget 1
```

Supply the skeleton object and the proof object, not a whole case container.
Examples containing both are under `cases/replay/`; the evidence format and
trusted dependencies are specified in `proofs/optimization-replay.md`.

## Results, proofs and provenance

The original campaign records 135,200 accepted-candidate execution comparisons;
the export extension records 212,592 comparisons, without disagreement in
their declared finite domains. These are abstract schedule/observation checks,
not physical speedups or a general mechanized proof. The full-recovery
constructor's negative result remains in the proofs and results.

`results/` retains JSON/CSV measurements, witnesses and raw logs.
`results/current-replay/` separately retains the native 44-stage campaign with
its 52-method suite; current quick checks include later regressions. Historical
timings and paper-table inputs remain in the original `results/`.
`audit/` retains earlier raw clean-reproduction comparisons and diagnostic
witnesses. `claim_evidence_ledger.csv` links claims to their evidence and scope.

The sequential interpreter does not import the checker or target interpreter;
the direct-clock/resource oracles use separately expressed computations.
These are implementation separations, not independent authorship or external
review. Handwritten proofs retain their stated abstract semantics, including
unbounded mathematical integers; native arithmetic and allocation failures are
outside that model. Construction failure is not global infeasibility.

`external_resources.csv`, `literature/`, and `proofs/literature.md` preserve
source identities and reading/access boundaries. No third-party paper PDFs are
redistributed. Original code, cases, results and exposition are MIT-licensed;
see `LICENSE` and `licenses/README.md`. Publisher rights remain upstream.

Substantive AI assistance was used for formulation, literature screening,
proof drafting, code generation and revision, experiment orchestration,
analysis, validation and manuscript writing. The experiments execute the
included deterministic Python programs; they do not execute a language model.
