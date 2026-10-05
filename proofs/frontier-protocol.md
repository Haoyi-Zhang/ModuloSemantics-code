# Certified-export evaluation protocol

The export interface, two selection examples, the recurrence/tail-latency pilot,
and the fault-forwarding control were developed before this protocol. This is a
freeze of the subsequent evaluation design, not a preregistration claim for the
whole research project. None of the generators below is an industrial benchmark.
No model is trained. Seeds separate reproducible input streams, not human studies.

## Questions and planned checks

1. Selector existence: compare information-cell selection with independent
   enumeration of whole Boolean decision tables. Enumerate two atoms, two tickets,
   every pair of 4-bit goodness masks, ticket completions in {0,1}, atom releases
   in {0,2}, and observation times 0..3. Include pointwise clairvoyant coverage and
   a single globally good ticket as deliberately incomplete/unsound baselines.
2. Earliest time: for each release/completion/mask case compare critical-point
   search with enumeration of every integer time up to three. A separate seeded
   three-atom collection uses the same decision-table oracle but is not described
   as a distribution shift or as complete enumeration.
3. Storage: enumerate interval 1..8, export 0..12 and last use from export through
   export+3*interval+3. Search ring sizes explicitly by tagged write/read events.
   Include export-before-issue equal-time collisions; test one fewer cell.
4. Program semantics: four specified families (ordinary recurrence plus a slow
   tail; guarded recurrence; two mutually loop-carried source identities;
   functional tuple state) with trip counts 0..3 (0..2 for functional memory),
   every Boolean stream, and declared finite input/initial-value domains. Compare
   the unchanged sequential interpreter against the heap-event, direct-clock and
   tagged-bank executions for earliest and latest exports, on both waiting and
   full-replay skeletons. Publish failures, construction rejections and all counts.
5. Fixed-skeleton scheduling: distances {1,2,3,5}, tail latencies {1,3,7,15,31},
   actual releases {0,3,8}, capacities {1,2,4}. Both constructors receive exactly
   the same source/costs; attempted interval domain is 1..256. Compare retirement-
   only operands, copied retirement selectors at their earliest ready time, and
   newly synthesized information-aware selectors. No wall-clock speedup is inferred.
6. Generalization check: apply unchanged export synthesis to every one of the
   96 inherited sources, including originally failed constructions. Use all their
   retained execution inputs. Separately use nonuniform release times, distance
   64, and compound guards as boundary tests rather than calling them workloads.
7. Negative controls: expose an exported fault, reverse source retirement, use an
   undersized ring, export an unavailable or wrong ticket, omit a selector arm,
   overlap arms, use the wrong source or iteration distance, or consume before
   export. Retain concrete unequal/stuck witnesses where one exists; a checker
   rejection alone is not called a behavioral witness.
8. Reproduction: rerun the inherited 16-step campaign and all new steps after
   changes, then repeat from a clean archive extraction. Deterministic scientific
   values must agree; timings are measured again and need not match.

## Claims and failure policy

Zero finite discrepancies supports implementation consistency only. General
preservation, information-uniform selector completeness, interval inequalities
and labelled-bank sizes require separate handwritten proofs. The interpreters and
oracles are separately expressed but co-developed with substantive AI assistance.
No independent human or proof-assistant verification is claimed. An oracle
mismatch stops the step and writes the full case before any summary is produced.
All successes/failures are reported, not only improved intervals. No target
performance improvement is a gate. The old full-recovery negative result remains.

Only local standard-library Python execution is used, one worker per bounded
step under the inherited 3.5 GiB/40 CPU-second limits. Larger Cartesian domains
are split by semantic family, not truncated after favorable results. The protocol
is supplemented by exact inputs in cases/frontiers and raw CSV/JSON in results.

## Subsequent obligations and execution repairs

After the initial selection/feedback experiments, the analysis established a
complete-by-retirement cutoff, the canonical hybrid annotation theorem, and a
startup realization lemma for resources. These are subsequent explanatory and
constructive results, not preregistered discoveries. Their dedicated checks are:
all Ret/Forward annotations and all integer export times for four small coupled
feedback skeletons; budget-zero and cutoff checks on twelve skeletons; actual
issued-reservation witnesses before first retirement; replayed impossibility
cells; scaling across 0,2,4,6,8,10 atoms and 2,8,32 candidates; and explicit
counterexamples to reachability-based interpretations of conservative bank sizes.

The earlier 1..256 search plan is replaced, when C<=256, by the proved complete
1..C search. Larger C retains a visibly truncated representation flag. The
inherited 96-source job exceeded one bounded run during development before
completion. It is now split into eight fixed disjoint blocks of twelve sources;
the aggregator checks all 96 identifiers and all 384 policy records. No source
was removed because it failed construction. A first annotation-oracle execution
failed in its input adapter (Boolean streams supplied in the wrong shape), and
was corrected before successful reruns; it was not recorded as a scientific
success. These execution repairs do not change the frozen source sets.

This development has no held-out industrial workload and no claim of independence
from the evolving proof. The original 96 programs are inherited development
regressions. The strongest protection against generator-specific success is the
complete small decision-table and annotation oracles, combined with separately
expressed execution and deliberate incorrect alternatives. Scientific counters
and timing fields are refreshed by a final serial campaign and clean extraction;
no blanket PASS label establishes journal quality or novelty.

The final semantic-family rerun adds the canonical hybrid annotation as a third
policy alongside earliest and latest all-forward exports, on each of the two
unchanged constructors. This directly exercises the new optimization output in
all three execution paths. It does not replace a failed policy or select new
input domains; the six-policy counts are regenerated and supersede only those
four family output files. The inherited matrix keeps its original four policies.

The selector timing protocol now uses seven batches of 64 calls per
configuration (18 configurations), retaining CPU and wall time for every batch.
Individual-call measurements were susceptible to timer granularity. This is a
measurement repair, not a change of algorithm, instance domain or correctness
classification; the final campaign regenerates both scaling result files.
