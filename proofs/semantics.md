# Conditional certificates: mathematical specification and hand proofs

These are handwritten mathematical proofs, not a proof-assistant development.
The reference and target interpreters are separately implemented finite-test
oracles, not an independently authored verification. The proofs concern the
mathematical language below, assuming its primitives and storage behave as
specified; they do not prove every behavior of the Python runtime.

## 1. Source language and observations

Fix a finite ordered node set V, actual Boolean atoms A, predicted atoms H,
and a nonnegative finite trip count N. Each iteration i has a complete Boolean
valuation theta_i of A union H. Source guards mention only A. Valuations are
arbitrary and independent across iterations; no prediction-accuracy assumption
is made. Each node v contains a guard g_v, primitive f_v, ordered operands,
a fallback reference and an emission flag.

References name a current-iteration immutable input, an integer constant, or
(u,i-d), where d is a nonnegative integer. When d=0, u must precede v in V.
Negative-index references use supplied initial values. All root/initial values
are ordinary values, not fault tokens. Positive distances may refer to any
source node. This makes source evaluation well founded in lexicographic order.

Let D be the value domain, and E be a disjoint set of defined error reasons.
Primitives are deterministic total functions from lists of D+E to D+E. A
primitive receiving fault tokens propagates the first token in operand order;
otherwise it computes an ordinary value or a newly defined error. The concrete
artifact provides integer arithmetic, truncation-toward-zero division, and
functional tuple load/store. There is no implicit heap or externally visible
speculative store. Arithmetic integers are mathematical integers, not fixed-width
machine integers. Type, bounds and zero-divisor failures are defined errors.

Define a total shadow denotation D(i,v) by the source reference order. If g_v
holds, apply the lifted primitive to its operands' denotations. Otherwise use
the fallback denotation, without evaluating the primitive. This denotation may
extend beyond an error; it is a proof device, not the actual source execution.

Actual source execution visits (i,v) in lexicographic order. If D(i,v) is an
error e, it emits Fault(i,v,e) and stops before updating v. Otherwise it records
D(i,v), updates the last value of v, and emits Emit(i,v,D(i,v)) exactly when
both g_v and its emission flag hold. Its observation is the trace together with
the last-value map and terminal status. No result from after the first error is
observable. For N=0 the observation is an empty trace, empty state and Done.

## 2. Periodic target language

An attempt a has a source identity nu(a), nonnegative issue offset s_a, positive
latency l_a and Boolean activation alpha_a. It is issued in iteration i at
i*I+s_a, for a fixed positive initiation interval I. Each attempt is one of:

- Op: apply the primitive belonging to nu(a) to specified operands. Its actual
  activation may use predictions and need not imply the source guard.
- Copy: return the source node's fallback through a specified operand.
- Mux: select one complete ticket of the same source identity using a partition
  of Boolean selection guards, within the attempt's activation.

All attempts create private tickets containing either a value or an error.
They never emit source observations. Local ticket references point backwards in
the certificate list. An operand can instead use an immutable input, constant,
or retired value (u,i-d) with d>=1. Negative indices read initial values.
There are no unchecked cross-iteration speculative-ticket references.

A retirement batch occurs at i*I+C, with a fixed C>=0. For each source node in
source order, it selects one ticket according to that node's total retirement
partition. It then performs the source observation action just defined: stop on
an error, otherwise update and possibly emit under the actual source guard.
All remaining tentative work is cancelled on the first retired error. After
iteration N-1 retires successfully, execution terminates.

At a common clock, completions occur before retirement, which occurs before
new issues. Identifiers are opaque; pending and completed tickets are disjoint
maps, not strings in an overlapping name space. Storage is idealized: no claim
about finite rotating-register allocation or memory reclamation is made.

## 3. Finite obligations

Boolean implications below quantify over every valuation of A union H. A
predicate's syntactic atoms must be available whenever the expression is
evaluated. In particular, activation predicates are tested unconditionally,
mux selection predicates are tested whenever that mux is active, and retirement
selection predicates are tested whenever retirement is reached. A predicate
which is false still requires its atoms to be ready. This conservative rule
matches the expression evaluation contract; truth on the selecting path alone
is not an adequate readiness test.

Whenever an active operand is consumed, its declared source identity must
match the source reference exactly. This is syntactic identity, not a claim of
algebraic equivalence. Local references must name an active producer whose
completion is no later than the consumer's issue. Inputs must be released by
use. Retired references satisfy s_a >= C-d*I. Initial values are available at
time zero. Each active attempt completes by C. Mux selectors are pairwise
disjoint and cover the attempt's activation; retirement selectors partition the
entire Boolean valuation space. All selected local references name preceding
attempts. The actual source guard is available at retirement.

The checker computes conditional-goodness predicates gamma; it does not accept
user-supplied proofs of goodness. Let G(r) be true for a correctly identified
root or retired reference and gamma_b for a local ticket b. For an Op attempt
of source v,

    gamma_a = alpha_a AND g_v AND (AND over operands r of G(r)).

For a Copy attempt of v,

    gamma_a = alpha_a AND NOT g_v AND G(fallback operand).

For a Mux attempt with branches (beta_j,b_j),

    gamma_a = alpha_a AND (OR over j of (beta_j AND gamma_bj)).

For every retirement branch (beta,a) of node v, beta must imply gamma_a and
the ticket must have identity v and have completed. Shape, activation, identity
and timing obligations are checked separately, not hidden inside goodness.

The executable checker represents these predicates by exact truth-table
bitsets, with at most ten local Boolean atoms. This bound is an implementation
limit, not an assumption required by the finite-set mathematical theorem.

## 4. Availability lemma

**Lemma 1.** Before target termination, every issued active attempt can read
its required data and evaluate its predicates, and every reached retirement
can select an available ticket.

**Proof.** Traverse target events in clock order, breaking equal times as
specified. Activation expressions have all syntactic atoms available by their
issue offsets. If an activation is false, no operands or mux choices are read.
If it is true, a root reference is available by the input-release obligation,
and a constant or negative-index initial reference is available immediately.
For a local reference b used by a, activation inclusion ensures b was active
on this same iteration valuation. The strict positive producer latency and
s_b+l_b <= s_a imply that b was issued earlier and its completion precedes the
consumer; equality uses the completion-before-issue order. List order forbids
cyclic references. A mux evaluates its choice guards in its active context;
readiness, coverage and disjointness give one selected available producer.

For a retired reference with nonnegative source index j=i-d, d>=1 gives j<i.
The inequality C-d*I <= s_a is equivalent to j*I+C <= i*I+s_a. Thus the needed
retirement has already occurred, including at equal clock times. If that batch
had failed, the target would have terminated and the hypothesized later issue
would not occur. Otherwise it committed every source node. Negative-index
references instead use the initial map. Retirement selectors are available and
form a partition; the selected ticket is active because goodness includes
activation, and completes by the batch's clock. The source guard is also
available there. Therefore no missing-input, missing-ticket, early-predicate or
nonpartition event can make an admitted execution stuck. QED.

## 5. Conditional-value lemma

**Lemma 2.** Assume prior retirement actions are correct. Whenever a completed
ticket a from iteration i satisfies gamma_a(theta_i), its content is exactly
D(i,nu(a)), including the error reason when that denotation is an error.

**Proof.** Establish the claim by induction over issue/completion events, along
with correctness of already retired values. By Lemma 1, all consumed values
exist, even for attempts that are not good. For a good Op attempt, the source
guard holds. Each local operand's goodness is part of gamma_a, so the induction
hypothesis supplies exactly its source denotation. Source-identity checking
ensures the right node and iteration were selected. Roots and initial values
match by definition; retired references match by the retirement hypothesis.
The target applies the same deterministic lifted primitive to the same ordered
operands, giving precisely the source denotation. This also covers propagated
and newly generated errors, since the lifting and error reasons are fixed.

For a good Copy, the source guard is false and the operand has the source
fallback's denotation. Lazy source evaluation therefore returns that same
value or error without evaluating the primitive. For a good Mux, disjointness
and coverage supply its unique selected branch. Its branch's goodness follows
from gamma_a on the current valuation. The induction hypothesis gives a ticket
of the mux's source identity with the correct denotation, and the mux copies
the entire ticket, including any error. No substitution of a guessed numeric
value for an error is permitted. Buffering a result until completion changes
neither the result nor its denotation. QED.

This proof is not circular: same-iteration operands come from earlier completed
ticket events; nonnegative earlier-iteration references come from strictly
prior retirement events; initial values need no recursive hypothesis.

## 6. Trace-preservation theorem

**Theorem 1.** For every well-formed source, certificate satisfying the semantic
and availability obligations, finite N and well-formed input streams, the
mathematical target and sequential source have equal observations. This includes
successful termination and the same first defined error with the same preceding
trace and last-value state. Adding the resource obligations below establishes
declared resource-envelope feasibility, not a stronger observation theorem.

**Proof.** Maintain, over target events, the conditional-ticket invariant of
Lemma 2 and the invariant that retired source actions form precisely a prefix
of the sequential execution. Initially both maps and traces are empty; source
root and initial values agree. An issue or completion does not alter the
observable prefix. Lemmas 1 and 2 establish availability and goodness for each
new ticket using earlier events. These arguments require no assumption that a
wrong-path attempt is itself correct or nonfaulting.

At retirement, I>0 orders batches by iteration. Within a batch the source-node
order is fixed. A total, disjoint selector chooses a good ticket for the next
node, so Lemma 2 supplies its exact denotation. If it is an ordinary value,
both executions update the same last-value entry and emit the same event or
neither, under the actual source guard. If it is an error, both emit the same
fault label and stop before updating that node. Every earlier source action
was already matched and none faulted; hence this error is the first source
error, not merely an arbitrary error that happens to have the same reason.
The prefix invariant is preserved in either case.

For N=0, equality is immediate. For N>0, the target has finitely many issue
and retirement events and creates at most one completion per active attempt.
Primitives are total in the lifted semantics, so no event diverges. There are
no observable transitions other than retirement actions. The finite event
sequence therefore reaches either a matched fault or the final retirement.
All active attempts needed by a batch finish by its clock; after the final
successful batch the target and source both terminate. Cancellation removes
only private, unobserved tentative work. Thus traces, terminal statuses and
last-value maps coincide for all finite N. QED.

The theorem has no fixed-width arithmetic overflow, allocation failure,
side-channel, interrupt, memory-mapped I/O, arbitrary branch or concurrency
semantics. It does not turn a defined toy division fault into a safe hardware
speculation mechanism.

## 7. Exact resource envelope

Let each attempt reserve a named resource at a finite set of relative offsets
Delta_a contained in [0,l_a). For resource R and phase r in [0,I), group every
reservation record (a,delta) by

    s_a + delta = k*I + r.

Let B(R,r,k) be the resulting multiset of records. Distinct reservations count
separately, even when they belong to the same attempt. Define

    W(R,r,k,theta) = sum_{(a,delta) in B(R,r,k)} [alpha_a(theta)],
    P(R,r) = sum_k max_theta W(R,r,k,theta).

**Theorem 2.** P(R,r) is the exact maximum occupancy at phase r over all finite
trip counts and independent iteration-local Boolean activation streams. Thus
P(R,r)<=capacity(R) for every phase is necessary and sufficient for this
activation envelope. It can overapproximate fault-truncated executions.

**Proof.** At clock q*I+r, a record in stage k belongs to logical iteration
q-k. Grouping reservations by this equation partitions all occupants at that
clock. Within one stage every guard reads theta_(q-k), so its occupancy is
W(R,r,k,theta_(q-k)). Different stages correspond to different logical
iterations, hence their valuations can be chosen independently. Each stage's
occupancy is at most its local maximum; summing gives the upper bound P.
Boundary iterations outside [0,N) simply delete records and cannot increase it.

For tightness, let k_min and k_max be the least and greatest contributing
stages. Select q=k_max and N=k_max-k_min+1; then all q-k are distinct valid
iteration indices. For each k choose a local maximizing valuation, which
exists because the Boolean valuation set is finite, and assign it to q-k.
Their combination is a lawful independent stream and attains every stage
maximum simultaneously. Empty buckets have peak zero. Consequently a
capacity smaller than P has a witnessing envelope, while a capacity at least
P admits all envelopes. Fault cancellation may prevent that witness from being
an actual complete source run, which is why the theorem names the envelope.
QED.

Guard independence is essential. Two reservations with predicates p and not p
can overlap when they belong to different stages. For offsets zero and I,
u_q and v_(q-1) can both fire with p_q=true and p_(q-1)=false. Conversely,
complementary predicates within one stage cannot both fire. Neither counting
all records unconditionally nor testing all records against one iteration's
valuation is an exact general replacement for the formula.

## 8. A limitation of full recovery at fixed offsets

The artifact's Wait construction starts one actual-guarded replica at the
latest Boolean release R. Its Recover construction creates a guessed replica
starting at zero and an actual-guarded replica starting at R, activated only
when M is false, where M asserts equality of each actual/predicted pair.
Corresponding replicas use identical dependency topology and primitive costs.
Both choose C as the maximum nominal completion offset, including inactive
branches. Offsets are fixed before the initiation-interval search.

**Theorem 3 (constructor dominance).** For this exact construction,
C_Recover=C_Wait. For every positive interval I, if the Recover certificate is
admitted, then the Wait certificate at the same I is admitted. In particular,
Recover cannot improve the least admitted interval over the same search domain.
This is not a theorem about all speculative schedulers.

**Proof.** The actual replica in Recover and the sole replica in Wait have
identical offsets and completion times: proceed inductively over the common
operand DAG, noting that both earliest-time calculations start at R and take
the maximum of identical input and local-producer completion times. The guessed
replica starts no later, has the same operand topology and costs, and merely
renames guard atoms, which the offset calculation does not inspect. Its times
are therefore no later by the same monotone maximum induction. This proves
C_Recover=C_Wait.

Suppose there is at least one actual/predicted pair. For every actual valuation,
there exists a predicted valuation making M false, obtained by disagreeing on
one pair. On this extension, all active Wait attempts occur as the identically
positioned actual-replica attempts in Recover. At each resource phase and
stage, their occupancy is therefore no larger than the maximum occupancy of
Recover's bucket; its additional guessed reservations are nonnegative. Taking
local maxima and summing proves P_Wait(R,r)<=P_Recover(R,r) for every resource
and phase. Independent-iteration quantification permits a separate mismatching
extension at each stage.

The same extension argument transfers each conditional operand-activation and
timing obligation of Wait from the corresponding actual-replica obligation in
Recover. Their offsets, latencies, source identities, input releases and C are
identical. Guard readiness of Wait is guaranteed by its start at R, and local
source-identity goodness makes its mux output good under every actual
valuation. Its retirement selector is true. Hence all Wait checks pass. If
there are no Boolean pairs, there are no source guard atoms either, R=0, and
the guessed replica is itself identical to Wait; the recovery replica is
inactive. The same conclusion follows directly from that replica. Thus
admission of Recover implies admission of Wait in both cases. QED.

This theorem explains a negative result, not a speedup: duplicated recovery
and fixed worst-case retirement remove the opportunity sought by this particular
construction. Selective recovery, altered offsets, correlated prediction models
or dynamically earlier retirement are different constructions requiring fresh
proofs; none is silently included here.

## 9. Incompleteness and obligation controls

For the source a = p ? id(x) : x, both source branches return x. A target which
always retires its guessed replica is observationally equivalent because it
still uses the actual guard to decide emission. Yet the checker rejects it on
prediction-mismatch valuations: its structural goodness derivation does not
use id(x)=x. This proves that these sufficient obligations are not necessary
for arbitrary interpreted semantic equivalence. The finite 144-input check
is corroboration; equality of both branches is the general hand argument.

Omitted recovery and wrong source-value identities have concrete unequal-value
witnesses. Premature consumers, unavailable guards, missing retirement arms and
incorrect retirement times can instead become stuck; they must not be counted
as observed wrong numerical answers. Exposing tentative faults eagerly and
reversing retirement order violate the runtime contract despite an unchanged
certificate. Wrong iteration distances may also produce availability failures.
No global minimal-counterexample claim is made.
