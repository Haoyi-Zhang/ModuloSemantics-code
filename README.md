# Conditional certificates for periodic loops with deferred faults

This repository contains a restricted loop language, a structural certificate
checker, separately implemented sequential and event-driven interpreters, exact
finite oracles, deterministic generated inputs, and handwritten mathematical
proofs. It is a self-contained research artifact, not a production compiler or a
proof-assistant development. The investigation has **not passed Scientific Lock**:
a publication-level novelty/significance argument remains unresolved.

## Reproduce the recorded evidence

Use a POSIX system with Python 3.10 or later, the standard library, and at least
4 GiB memory available to the process group. No package installation, network,
GPU, model, external API, private data, or sibling paper directory is required.
Run from the extracted repository root:

```sh
python reproduce.py
```

The driver runs one child at a time, pins each experiment to one available CPU,
sets a 3.5 GiB address-space ceiling, and sets a 40-second soft / 44-second hard
CPU limit per child. A child exceeding its independent wall-time limit is
terminated and the reproduction stops. The existing result files are refreshed
only by the corresponding completed chunks. A slow machine may hit these
limits; that is a failed reproduction, not permission to lower coverage or
claim a pass. Linux records peak resident memory in KiB; other systems may use
a different unit for `ru_maxrss`, so the supplied resource interpretation is
Linux-specific. The driver's requested affinity and address-space limit do not
configure system swap; the original environment had no swap, and a new
reproduction environment must satisfy that condition separately.

For bounded batches in a tool environment, keep the extracted code unchanged
and run the following serial commands. The first starts fresh; the others
resume the recorded completed prefix. `--resume` does not certify that files
have remained unchanged; re-extract and restart after any code modification.

```sh
python reproduce.py --max-steps 5
python reproduce.py --resume --max-steps 5
python reproduce.py --resume --max-steps 5
python reproduce.py --resume
```

For isolated diagnostic chunks (these do not accumulate a full-run pass):

```sh
python reproduce.py --step tests
python reproduce.py --step guarded-division
python reproduce.py --step generated
python reproduce.py --step dominance
python reproduce.py --step reconcile
```

The final reconciliation compares a scientific expected result object, not a
checksum or machine fingerprint. It checks all retained counts and invariants.
Timing fields are measured afresh and are intentionally not expected to match.
`results/reproduction.json` records exactly which driver steps completed; only
a successful complete step sequence, uninterrupted or resumed on unchanged
files, constitutes clean reproduction. The full command
does not download or rerun third-party systems.

To check a certificate, without executing either program:

```sh
python -m semantic_certificates cases/guarded-division.json
```

The JSON output contains acceptance, diagnostics with falsifying local Boolean
valuations, computed goodness masks, and phase/stage resource witnesses.
Exit status is 0 for acceptance and 2 for rejection or a handled input error.
The command-line reader rejects duplicate JSON keys and files above 4 MiB.
`guard_ready` and `input_ready` must be JSON objects whose keys exactly match
the declared atoms and inputs. Every release is a JSON integer from 0 through
4096; JSON Booleans are not integers for this purpose. Arrays, strings, `null`,
a missing or extra key, and a non-integer release are returned as
`accepted: false` with a `format` diagnostic rather than reaching mapping
operations or producing a traceback.
An optional `--input path.json` compares the two executions after admission;
this option assumes the well-formed finite input format described below. It is
not an adversarial execution sandbox. The bounded reproduction driver should
be used for the experimental campaign.

## What the results establish

The mathematical proof in `proofs/semantics.md` establishes a sufficient
conditional-ticket criterion for preservation of traces, the first defined
fault, and last-value state in the declared abstract semantics. It proves an
exact resource bound for the independent-iteration **activation envelope**,
which can exceed occupancy of runs truncated by a fault. A third handwritten
proof explains a null result: the supplied full-recovery constructor cannot
improve the least admitted initiation interval over its Wait counterpart on a
common period domain. This is a limitation of that constructor, not of all
speculative scheduling.

Finite checks are not general mechanized proofs. The sequential interpreter
imports neither the checker nor the target interpreter; the target interpreter
does not call the checker. The reservation oracle explicitly unrolls clocks
rather than using the checker's phase/stage quotient. These code separations
reduce some shared implementation risks, but every component was developed in
the same development session. There was no independently authored or
external blind verification.

The recorded main matrix has 132,608 accepted-candidate comparisons from eight
exhaustive schemas and 2,592 comparisons from admitted schedules of 96 generated
schemas: 135,200 comparisons, with no difference in the defined observations.
The generated denominator is all 96 schemas, not just successful constructions.
Recover admits 46, Wait admits 62. Among the 46 pairs, Recover has a larger
initiation interval in 43 and ties in 3; its retirement offset ties in all 46.
These are declared abstract schedule costs, not elapsed program performance.

A separate 216-certificate grammar is checked against all 108 one-iteration
inputs per certificate (23,328 comparisons). It admits 4 certificates and
rejects 212, without a classification discrepancy in that finite domain.
Rejected certificates intentionally have counterexamples; these comparisons
are not included in the 135,200 no-mismatch total. The resource-component
matrix contains 1,728 instances, 2,376 phase/resource cells and 90,720 Boolean
stream assignments. It is not a corpus of 1,728 fully admitted programs.

Seven certificate mutations are rejected and have retained witnesses. Two
execution-contract controls expose eager fault observation and reversed
retirement order. An algebraic identity gives a semantically correct rejected
schedule; the checker is not generally complete or necessary. The 6,144-pair
constructor test is a post-result falsification of the explanatory dominance
lemma, not a retroactively preregistered speedup experiment.

## Certificate model and input format

A certificate is a JSON object with exactly these top-level fields:
`actual`, `predicted`, `guard_ready`, `inputs`, `input_ready`, `nodes`, `costs`,
`resources`, `ii`, `retire`, `attempts`, `retirement`. The fully enumerated
examples under `cases/` are the executable schema examples. Unknown fields are
rejected rather than silently interpreted as a trusted assertion.

Actual and predicted atoms are disjoint named Boolean streams. A predicate is
a JSON Boolean, a declared atom name, `['not', e]`, `['and', e1, ...]`, or
`['or', e1, ...]` (using JSON double quotes in a file). Source guards mention
actual atoms only. Input and guard release times are offsets relative to the
logical iteration's nominal start. Predicate readiness is required even when a
predicate evaluates to false; mux choices require readiness whenever that mux
is active, and retirement choices whenever retirement is reached.

A source node has `name`, `guard`, `op`, `args`, `fallback`, and Boolean `emit`.
A reference is `{"input":"x"}`, `{"constant":1}`, or
`{"node":"v","distance":d}`. Distance zero requires a preceding source
node. Positive distances name earlier iterations; negative resulting indices
are read from the supplied initial map. Supported primitive behavior is integer
identity/add/subtract/multiply/truncating division and functional tuple
load/store. Ill-typed operations, bounds errors and division by zero yield
defined fault tokens. Source evaluation is lazy in the guard and stops at its
first fault. A false guard still defines the node through its fallback.

An attempt has `name`, source `node`, `kind`, `when`, and `offset`. The kinds
`op` and `copy` have `args`. A `mux` has `choices`, each containing `when` and
`attempt`. Local attempt references use `{"attempt":"a"}` and must point
backwards in the list. Cross-iteration references use
`{"retired":"v","distance":d}` with d at least one. They cannot name
unretired speculative state. Retirement maps each source node to a total,
disjoint list of choices of its own identity. Attempts emit no source events;
only retirement does. All values, including faults, are private until chosen.

Each cost record has positive `latency`, a named `resource`, and distinct
integer `reserve` positions from zero through latency minus one. These are
user-declared abstract costs, not measured processor properties. Resource
capacities are positive integers. An attempt at offset s in iteration i issues
at i*ii+s. Its selected operands must be available then. The iteration retires
at i*ii+retire. At equal clock times, completions precede retirement, which
precedes issues. This tie rule is part of the proof, not an incidental sorting
choice.

A well-formed execution input has nonnegative integer `n`; Boolean lists of
length n for all declared atoms under `guards`; value lists of length n for all
`inputs`; and `initial[node][negative_index_as_string]` for every reached
negative source index. All inputs are ordinary values, never fault tokens.
The supplied experiments use integers and flat integer memory arrays; JSON
arrays are converted into functional tuples by the interpreters. Integer
arithmetic is unbounded in the mathematical semantics. Python allocation
failure and native machine arithmetic are not covered by the theorem.

Implementation caps are at most 10 local Boolean atoms, 64 source nodes,
512 attempts, initiation interval 1--256, offsets and releases 0--4096,
dependence distances 0--64 (retired target references 1--64), latency 1--128,
and capacity 1--256. Formula depth and arity are bounded in `logic.py`. These
are admission/representation limits, not experimentally established limits on
all possible modulo schedules.

## Repository map and evidence selection

`semantic_certificates/checker.py` implements structural checks and computed
goodness. `reference.py` and `target.py` implement the distinct executions.
`resource_oracle.py` is the finite unrolling oracle. `builders.py` contains two
untrusted fixed-offset constructions; they search only the interval dimension.
A construction failure is retained with the last candidate, the searched
interval bound and diagnostics. It is not a proof of global infeasibility.

`experiments.py` specifies all exhaustive domains and generated inclusion rules.
`certificate_oracle.py` defines the complete 216-certificate grammar.
`dominance.py` performs the exploratory 96-by-64 implication test.
`summarize.py` reconciles all tables into `results/summary.json`.
`tests/test_semantics.py` remains byte-for-byte unchanged and contains the
original 18 focused checks, including two retained implementation regressions.
`tests/test_format_validation.py` adds three API/CLI methods for the F1 format
boundary: same-name arrays, strings, `null`, exact availability keys, strict
integer releases, and the normal object case. A targeted post-repair run passed
the original 18, the new three, and all 21 under discovery; the exact output is
`results/unit-tests.txt` and the direct probes are in
`results/f1-format-validation.json`. A standalone `verify_results.py` pass
reconciled retained counts and stored cases against the current checker; it did
not regenerate experiments or recertify the full 16-stage sequence. The
regressions preserve the actual witnesses,
not a claim that the repaired implementation is now generally proved correct.

`cases/generated/` contains all generated source schemas, admitted certificates,
construction-failure candidates and exact sampled execution inputs. The fixed
seed is 72913; each schema has 24 cases with trip counts 0--12 and integer
inputs from -3 through 3. Exhaustive families are regenerated by nested products
of explicit literal domains, including all Boolean streams at the stated bounds;
no external dataset or omitted cache is required. Their exact dimensions are
also stored in their result JSONs. `cases/certificate-oracle/` preserves the
finite certificate grammar members and semantic classification witnesses.
`cases/counterexamples/` preserves mutations, incompleteness and bug witnesses.

The resource matrix and generated comparison have CSV rows alongside aggregate
JSON. `claim_evidence_ledger.csv` states the maturity and scope of each material
claim. `external_resources.csv` distinguishes read scholarly passages, indexed
metadata, blocked full-text access, and supplied template assets. No baseline
internals or third-party research code have been modified or integrated.

## Limits, provenance and licensing

Original implementation, generated cases, results and exposition carry the MIT
notice in `LICENSE`. Upstream publisher and author rights remain with their
owners. No external research-paper PDF is redistributed; bibliographic source
identifiers and access limitations are retained instead. The repository does
not require the publisher template. The project paper separately retains the
supplied ACM class/style and their unmodified LPPL notice.

The 12 same-venue / 5 influential / 5 adjacent full-paper calibration is not
complete. The original Lam source full text and live TOPLAS guide were not
successfully retrieved at their supplied endpoints. Modern validation and
predication work already blocks broad novelty claims. The current manuscript
is an internal technical record rather than a completed 50-page TOPLAS article.
