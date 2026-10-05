# Replayable fixed-skeleton optimum

## Problem and trust boundary

The input is the same fixed skeleton S, Boolean releases, primitive costs,
resource capacities and source observation contract as Theorem H in frontiers.md.
Only the positive period I, Ret/Forward annotations and optional export declarations
may change. A budget B counts the sum of separate uniform tagged forwarding-bank
cells; it does not count all storage. S is provided to the consumer independently
of the proposed proof. A producer may not change S and call the change an
optimization. All mandatory sets use satisfiable activation contexts, as in H.

A proof declares a budget, either a positive minimum J or no feasible period,
and a consecutive list of per-period rows. A positive proof has exactly the rows
1,...,J. Its last row supplies an admitted target with a recomputed bank count
that equals H's lower bound and fits B. Every earlier row gives one exclusion:
(a) a resource/phase whose independently recomputed envelope exceeds capacity;
(b) an information-cell obstruction at a mandatory source's latest deadline U_v;
or (c) the mandatory-lifetime lower bound exceeds B. The verifier recomputes
masks from the semantic checker, not from producer assertions. It does not call
selector search, annotation search, or the production bank-layout routine.

The verifier trusts the implementation of the semantic checker, TruthTable,
validation-only problem parsing, obstruction replay, ordinary integer arithmetic,
and the handwritten results H, B and C. Separate functions are not independent
provenance or machine-checked assurance. Both producer and consumer were developed
with substantive AI assistance. No whole-program resource or timing speedup is
inferred from replay acceptance.

## Theorem P: sound budget optimum replay

If replay accepts a positive proof J for S and B, J is the least positive period
admitting an annotation within B cells in the mathematical class of Theorem H.
If replay accepts a negative proof through max(1,C), no positive period admits
such an annotation. A negative proof stopped by the prototype cap at 256 when
C>256 establishes only nonexistence for I in 1,...,256.

Proof. For a resource exclusion, changing Ret/Forward annotations and exports
leaves activations, primitive reservations, offsets and costs unchanged. The
same violating resource cell therefore excludes every annotation at that I.
For an obstruction at U_v, replay supplies a single observable-information class
and excludes every candidate, by a late completion or an explicit bad valuation
consistent with that class. No selector exists at U_v. By information monotonicity
none exists at an earlier admissible export time. Mandatory forwarding requires
F_v<=U_v, so no annotation is admitted. For a budget exclusion, every annotation
must forward all mandatory occurrences. Its first/last lifetime endpoints obey
F'_v<=U_v and L'_v>=L_v, so the separate-bank lower bounds add to a cost greater
than B. This excludes every budget-feasible annotation even if some selectors
are themselves unavailable.

For the last positive row, exact structural comparison preserves S after erasing
only I, export declarations and Ret/Forward tags. The semantic checker admits the
target at J, hence proves the model-level observation obligations conditional on
its correctness. The replay routine recomputes every forwarding lifetime and
checks the stated total against H's lower bound and B. The target is thus a
budget-feasible witness, and is storage-minimal at J. All smaller positive
integers appear exactly once and have valid exclusions. Consequently no smaller
period works, without assuming monotonic resource admission. Periods greater than
J cannot improve the least-period objective, even when C exceeds the prototype
cap. For a negative proof through C, Theorem C excludes every larger period by
reducing it to C, completing the unbounded conclusion. Without reaching C that
last implication is not available. QED.

## Relative completeness and limitations

For a well-formed fixed skeleton whose supported domain reaches C, exact Boolean
mask evaluation gives one of the three exclusions at every budget-infeasible
period: first resource failure; otherwise, if a mandatory selector fails, its
finite obstruction; otherwise all selectors exist and H gives the exact minimum,
which must exceed B. At the first feasible period H supplies the positive row.
This is completeness of this evidence format relative to the existing language,
masks and annotation theorem, not of arbitrary program equivalence or arbitrary
scheduling. A bounded implementation may reject oversized or malformed objects.

Replay can be as expensive as checking every period in the prefix. No asymptotic
or measured speed advantage over optimization is asserted. Its purpose is to avoid
trusting an optimizer's search completeness, period skipping, reported optimum,
input identity or scalar bank count. General Boolean and resource checking remain
in the trusted consumer; the proof is not a constant-size machine certificate.

## Executed-domain protocol (fixed before the new matrix was run)

* Selector extension: all three candidate masks on two atoms (16^3), each of
  three completion times chosen from {0,2} (2^3), releases p=0,q=2 and query t=1.
  This is 32,768 finite cases, not an industrial or statistically independent
  holdout. Compare with the pre-existing separately expressed whole-decision-table
  oracle. For each infeasible case replay an obstruction and reject a deliberately
  damaged excluded-candidate map. Retain representative witnesses and all case
  classifications. Do not change the checker in response without documenting it.
* Small optimum oracle: four existing cross-feedback skeletons, release in {0,2},
  tail latency in {3,7}; compute all annotation/export-time optima for every period
  1,...,C+1 with the independent enumerator. For each bank budget 0,...,6, replay
  the proposed least-period proof and compare it to the enumerated optimum.
* Structured transfer: two constructors, recurrence distance in {1,2,4}, release
  in {0,3}, tail latency in {3,9}, and capacity in {1,4}; all 48 skeletons and three
  budgets {0,1,3}. Keep any constructor failures as inputs, and report unexpected
  skeleton failures rather than silently dropping them. Compare producer and
  consumer with the registered normal-form search, clearly not a second independent
  mathematical oracle. Store exact proof inputs and decisions.
* Regression: malformed release/candidate headers, skipped and reordered periods,
  altered budgets/counts/source/capacities, missing witnesses, invalid JSON values,
  CLI exit 0/2 and parseable JSON, plus the cap-truncated negative result. Tests
  ensure replay does not call selector/annotation search or production bank layout.

No favorable scheduling result or particular number of accepted proofs is a
prerequisite. All counts and timings in the manuscript are populated only after
executing the new tasks and reproducing them in a clean extraction.
