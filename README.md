# Conditional certificates for periodic loops with deferred faults

This repository contains a restricted loop language, a structural certificate
checker, separately implemented sequential and event-driven interpreters, exact
finite oracles, deterministic generated inputs, and handwritten mathematical
proofs. It is a self-contained research artifact, not a production compiler or a
proof-assistant development. The current manuscript develops certified early exports, information-uniform
selector synthesis, a canonical Ret/Forward annotation minimizing separate
forwarding banks, and a complete-by-retirement period cutoff. These are restricted
model-level results, not external peer review or a guarantee of publication.
Recent neighboring verification systems and remaining full-text access limits
are recorded in `literature/reference-audit.json`.

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
python reproduce.py --max-steps 1
python reproduce.py --resume --max-steps 1
# Repeat the resume command until all 44 steps are recorded.
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
reduce some shared implementation risks but retain shared mathematical
conventions and development history.

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


## Certified exports and canonical annotation

`proofs/frontiers.md` specifies the extension and its proofs. The following
example runs locally from the repository root. It saves an admitted canonical
certificate; it is not an external compiler integration.

```python
import json
from semantic_certificates.builders import instruction, make_program, build, inp, node
from semantic_certificates.checker import check
from semantic_certificates.frontiers import hybrid_at, hybrid_design_space

source = make_program([
    instruction("s", "add", [node("s", 1), inp("x")], True, emit=True),
    instruction("t", "div", [inp("z"), inp("y")], True, emit=True),
], release=0, div_latency=12, capacity=4)
skeleton = build(source, "wait")
certificate, plan = hybrid_at(skeleton, 1)
assert check(certificate).accepted
with open("certified-export.json", "w") as f:
    json.dump(certificate, f, indent=2)
space = hybrid_design_space(skeleton, cell_budget=1)
print(space["minimum_budget_feasible_ii"], space["pareto"])
```

The selector interface `selection_at` computes a common good completed ticket
for every assignment of released atoms. `earliest_selection` searches release
and completion times. `obstruction_at`/`verify_obstruction` produce and replay
an information-cell refutation. Both public entry points explicitly validate
release/candidate objects, exact keys and strict integer ranges. An invalid
model or witness returns false from the replay function; unexpected implementation
exceptions are not hidden by a catch-all handler.
`hybrid_at` forwards exactly the satisfiable carried uses with deadline below
retirement, exports at the latest mandatory deadline, and checks the resulting
certificate. `hybrid_design_space` enumerates the proved finite period domain,
reports its Pareto set, and flags truncation when retirement exceeds the
representation's maximum period 256.

`frontier_oracle.py` contains separately expressed whole-decision-table,
tagged-lifetime, complete-annotation and direct-clock checks. It imports neither
the production checker/target/frontier module nor their model classes. The
implementation separations are described above. The original two interpreter paths
and the new direct-clock path are not three unrelated real compiler back ends.

The 44-step reproduction reruns the original campaign, export/annotation checks
and optimum-proof replay. The suite has 51 methods: the original unchanged 21,
the existing 21 frontier methods and nine new replay/format methods.
New evidence includes 17,408 fixed-time selector queries, 4,096 earliest-time
queries, 1,820 labelled storage cases, and 32 complete small annotation queries
with 512 assignments and 13,346 export-time vectors. Four concrete feedback
families compare six policies across three execution paths (195,408 comparisons).
Together with inherited-source forwarding, boundary runs and annotation
executions, new target comparisons total 212,592. Finite agreement is not the
proof of the general theorem. See raw results and `proofs/frontier-protocol.md`
for every denominator, input domain, failure rule and development limitation.

No GPU, model API, external solver or third-party compiler is invoked. No
industrial workload is called a holdout, and no physical speedup is inferred.
The old full-replay negative theorem remains valid for its retirement-only
premises. The new startup resource witness strengthens universal admission
under complete-by-retirement; it does not identify a chosen fault-truncated
run's peak or its minimum actual storage with the unconditional envelope.

## Certificate model and input format

A certificate is a JSON object with these required top-level fields and optional `exports`:
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
`{"retired":"v","distance":d}` with d at least one. They cannot name arbitrary unretired speculative state. An explicit
`{"forward":"v","distance":d}` instead reads a separately checked private
export of the same source value-or-fault ticket. `exports[v]` contains exactly
`offset` (0..retire) and a total disjoint `choices` partition. Its selected
same-source tickets must be good and complete, and the selector may mention
only atoms released by that offset. Retirement maps each source node to a total,
disjoint list of choices of its own identity. Attempts emit no source events;
only retirement does. All values, including faults, are private until chosen.

Each cost record has positive `latency`, a named `resource`, and distinct
integer `reserve` positions from zero through latency minus one. These are
user-declared abstract costs, not measured processor properties. Resource
capacities are positive integers. An attempt at offset s in iteration i issues
at i*ii+s. Its selected operands must be available then. The iteration retires
at i*ii+retire. At equal clock times, completions precede exports, exports precede retirement, and retirement
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
integer releases, and the normal object case. Those unchanged 18 semantic and
three format methods are included in the current 51-method suite; its actual
output is `results/unit-tests.txt`. The earlier direct format probes remain in
`results/f1-format-validation.json` and are not relabelled as a regenerated task.
The current 44-step driver reruns the inherited scientific campaign and both
extensions. In contrast, running `verify_results.py` alone only reconciles stored
counts and cases; it does not rerun the campaign. These regressions preserve
actual witnesses, not a claim that the Python implementation is generally proved.

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


## Replaying a budget-optimum claim

`proofs/optimization-replay.md` specifies the evidence format and proof. The
producer `optimization_witness.certify_budget` creates consecutive exclusion
rows and a checked winning certificate. The consumer
`optimization_replay.verify_optimum` takes the fixed skeleton and budget as
external inputs. It does not call selector search, annotation optimization or
the production bank layout. It still trusts the semantic checker, Boolean table
calculation, obstruction replay and the stated handwritten normal-form theorem.

From the repository root, this example regenerates and replays a stored case:

```sh
python - <<'PYCODE'
import json
from pathlib import Path
from semantic_certificates.optimization_witness import certify_budget
from semantic_certificates.optimization_replay import verify_optimum
case = json.loads(Path('cases/replay/matrix-recover-2-3-9-4-1.json').read_text())
proof = certify_budget(case['skeleton'], 1)
result = verify_optimum(case['skeleton'], 1, proof)
assert result['accepted'] and result['minimum_period'] == 4
print(json.dumps(result, indent=2))
PYCODE
```

For separate JSON files, the CLI is:

```sh
python -m semantic_certificates.optimization_replay skeleton.json proof.json --budget 1
```

The first file is the fixed skeleton object, not a whole case container; the
second is its `proof` object. The API returns structured acceptance or rejection.
The CLI emits JSON and exits 0 on acceptance, 2 on input/evidence rejection.
This offline research API is not a general hostile-file execution sandbox.

The full campaign runs three additional tasks and their reconciliation:

```sh
python run_bounded.py -m semantic_certificates.replay_experiments three-tickets
python run_bounded.py -m semantic_certificates.replay_experiments small-oracle
python run_bounded.py -m semantic_certificates.replay_experiments structured
python run_bounded.py verify_replay.py
```

Executed finite domains: 32,768 three-ticket queries, 28,279 replayed obstructions
and damaged-witness rejections; 28 independent-oracle budget queries; 144
structured queries (126 positive and 18 negative optima) and 540 rejected proof
mutants. The 512 annotations / 13,346 export-time tuples in the small oracle
reuse the earlier exact domain; they are not a new workload or additional
source/target comparison count. The structured grid compares the producer,
consumer and normal-form optimizer, not an independently authored system.
A negative proof truncated at 256 when C exceeds 256 explicitly reports bounded
scope. Positive proofs can still establish a global minimum below that cap.

## Limits, provenance and licensing

Original implementation, generated cases, results and exposition carry the MIT
notice in `LICENSE`. Upstream publisher and author rights remain with their
owners. No external research-paper PDF is redistributed; bibliographic source
identifiers and access limitations are retained instead. The repository does
not require the publisher template. The project paper separately retains the
supplied ACM class/style and their unmodified LPPL notice.

Substantive AI assistance was used for formulation, literature screening,
proof drafting, code generation and revision, experiment orchestration,
analysis, validation and manuscript writing. The experiments execute the
included deterministic Python programs; they do not execute a language model.
