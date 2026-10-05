# Causal certification and private forwarding

These are handwritten, AI-assisted mathematical arguments for the abstract
language. They are not a proof-assistant development. The implementation and
separately expressed finite oracles were co-developed. Finite tests are listed
separately and are not premises of the general theorems below.

## Definitions and inherited premises

Fix a nonempty, finite, source-ordered list V of definitions, disjoint finite
actual/predicted atom sets A,H, release map r, and a finite counted trip N. Let
Theta be all valuations of A union H. Every iteration independently receives a
valuation and ordinary inputs. The total shadow denotation D(i,v) is the
well-founded source expression, using source order for distance zero and smaller
iteration for positive distance; negative indices use supplied ordinary initial
values. Lifted primitives are deterministic total functions on ordinary values
plus defined error reasons, propagating the first error operand. The sequential
machine stops at its first defined error and otherwise emits/updates in source
order. Shadow values beyond that error are mathematical values, not continued
source execution. They permit reasoning about private future computations.

A skeleton fixes source definitions, attempts in backward-reference order,
activation and choice predicates, positive operation latencies, issue offsets,
source identities, local wiring, retirement choices and a common retirement
offset C. All non-resource, non-carried-timing baseline obligations hold. In
particular each satisfiably active attempt a completes at e_a=s_a+ell_a<=C;
local inputs and predicates are ready; selected local producers are active and
complete before use; retirement selections are total, disjoint and conditionally
good. Boolean releases and offsets are integers. Attempts and guards do not
change when carried operands are reannotated. Each carried operand occurrence
has a source identity v, positive distance d, issue offset s, and a satisfiable
activation context (permanently inactive occurrences need no timing obligation).

Let gamma_a be the structurally derived conditional-goodness set: an operation
uses its actual source guard and operand goodness; a copy uses its complement
and fallback goodness; a mux takes the disjoint selected good branch. Initial,
input, retired and certified-forward references have goodness true when their
identities match. Treating a forward reference this way is a *local assumption*
which the event-order theorem discharges jointly with export correctness; it is
not an assumption that a proposed export is already correct.

A candidate for source v is an attempt a with that source identity, completion
e_a, and derived gamma_a. No arbitrary supplied assertion of correctness is used.
The semantic language permits finite Boolean expressions. The prototype further
caps atoms, expression depth, offsets and periods and rechecks every synthesized
certificate, so mathematical existence outside those caps is not an executable
admission claim.

## 1. Uniform selection under released information

At time t define K_t={x:r(x)<=t}, and theta~_t theta' iff they agree on K_t. A
causal Boolean-only selector is a total map S from Theta to candidates, constant
on every equivalence class, selecting a with e_a<=t and theta in gamma_a. It
cannot inspect ordinary values, fault reasons or unreleased atoms.

**Theorem U (exact relative selection).** Such a selector exists iff every
nonempty ~_t class Z has at least one candidate a with e_a<=t and Z subset gamma_a.

*Proof.* A causal selector has one value a on Z. Completion and goodness for all
members give the inclusion. Conversely choose one admissible a per class. There
are finitely many classes; their known-atom conjunctions form a total disjoint
partition. Disjoin classes assigned to the same a. These expressions mention
only K_t, and their selected candidates satisfy completion and goodness. They
therefore encode a valid export partition. This proves both directions without
assuming arithmetic completeness of gamma. Empty candidate sets cannot satisfy
a nonempty class. With no atoms, there is one class; with no known atoms, one
candidate must be good on all Theta. QED.

**Counterexample to clairvoyant coverage.** Two ready tickets have goodness p and
not p, where r(p)>t. Their union is true, so every full valuation has a good
candidate. There is nevertheless only one information class, neither candidate
covers it, and no causal selector exists. Choosing by p would read the future.
Conversely, after p is released these tickets provide a selector even though no
single ticket is globally good. Both errors have executable ablations.

**Corollary U1 (earliest certification).** Selector existence is monotone in t.
An earliest nonnegative time, when one exists by C, occurs at zero, an atom
release, or a candidate completion. It is found by inspecting those times.

*Proof.* A later time only adds completed candidates and splits information
classes. An earlier class's witness candidate still covers each subclass.
Between consecutive release/completion events, candidates and classes are
unchanged. Nonnegative integer time has a least successful event if any. QED.

**Theorem U2 (negative witness).** Nonexistence at t has a finite witness: one
assignment to K_t and, for every candidate, either its completion after t or a
full valuation extending that assignment and outside its goodness. A replay that
checks all names, full Boolean valuations, extensions and inequalities certifies
nonexistence. The witness need not use the same bad valuation for every ticket.

*Proof.* A failing information class from U contains a bad valuation for each
completed candidate. Conversely the supplied known assignment defines a nonempty
class because every Boolean extension is permitted. Every candidate is either
not ready or fails somewhere in the class. No common candidate exists; U applies.
A selector at E and an obstruction at E-1 certify minimality; for E=0 the
nonnegative-time boundary replaces the obstruction. QED.

This is a finite observation-uniformity argument, not a claim to a new general
theory of partial-information strategies. Its use here is to connect ticket
correctness, releases and periodic carried-dependence deadlines.

## 2. Forwarding semantics and preservation

An export for v fixes F_v in [0,C] and a total disjoint causal selection of
same-source tickets, each complete and good whenever selected. At iI+F_v the
selected whole value-or-error ticket enters a private map X(i,v). Export has no
trace or last-state effect. A forward operand (v,d), d>=1, reads X(i-d,v), or the
ordinary initial value if i-d<0. It must satisfy F_v-dI<=s at every satisfiable
use. A retired operand instead satisfies C-dI<=s and reads the committed map.
At equal clock times, completions precede exports, exports precede retirement,
and retirement precedes issues. All operations have positive latency. A fault is
visible only when the source-ordered retirement visits its selected ticket; it
then cancels all private work and terminates. Retirement times increase strictly
with iteration because I>0.

**Lemma A (availability).** Until termination, every reached active issue,
export and retirement action has its required values and predicates available.

*Proof.* Induct through the finite chronological event sequence. Strict support
checks release every atom before it is tested, including atoms in a false branch
predicate. Inactive attempts do not evaluate their operands or mux choices.
Inputs and constants are available by their checks. Local producer completion
precedes use: positive latency and the completion inequality imply strictly
earlier issue, and equal completion time is ordered before issue. Producer
activation inclusion supplies the needed producer in this iteration.
A nonnegative carried index j=i-d is less than i. The forward inequality places
jI+F_v no later than the consuming issue; at equality export has priority. Every
export is scheduled independently of activation and has a total partition;
its selected ticket has already completed. The retired inequality is analogous.
If the earlier retirement had faulted, the hypothesized later event would not be
reached. Negative indices need no producer event. Mux, export and retirement
partitions choose one available active parent by coverage, disjointness,
completion and their respective readiness checks. An export cannot read another
export directly: it selects a local ticket whose positive-latency production has
already finished. There is thus no same-time cyclic justification. QED.

**Theorem S (all-finite-prefix observation preservation).** Every certificate
satisfying the extended semantic obligations has the same emitted trace, last
source-visible state and first defined fault as its sequential source, for every
finite trip count and well-formed streams. Resource capacities are not premises
of this semantic theorem.

*Proof.* Use one joint induction over the event sequence, maintaining: (T) each
completed good ticket of source v in iteration i equals D(i,v); (X) every private
export X(i,v) equals D(i,v); and (R) committed actions are a source prefix with
the same state, trace and termination status. The empty configuration satisfies
all three invariants. Negative initial values and immutable roots agree.
At issue, Lemma A supplies every operand. If gamma_a holds, the correct source
branch holds and each local operand is good. Earlier (T) gives the local values;
(X) gives forward values; (R) gives retired values; roots and source identities
supply the remaining cases. Applying the same deterministic lifted primitive to
the same ordered arguments gives D(i,v), including an error reason. Copy uses
the selected fallback; mux transfers its selected entire parent ticket. The
pending result is private, and its later completion establishes (T). A bad ticket
has no required relationship to D, and may be an error.
At export, the selected parent is good under the actual valuation and already
completed. Earlier (T) gives D(i,v), establishing (X) without changing (R). If it
is an error, subsequent private computation may propagate it; it remains private.
This argument can concern shadow definitions after the source's eventual first
error. It does not claim that those source actions have executed.
At retirement, batches are in increasing iteration order and each batch visits
V in source order. Its selected parent is good and available, hence equals the
next source definition. An ordinary value updates the same last-state entry and
emits under the same actual guard. An error appends the same labelled fault,
before updating that definition, and terminates both machines at their first
unmatched source position. Cancellation cannot undo earlier public actions or
publish later private ones. These cases preserve (R).
The joint induction is well-founded in actual event order: ticket proofs use
completed producers or earlier exports, and exports use already completed
tickets. No correctness of a future export is assumed. Abstract lifted
operations terminate; the queue contains finitely many initial events and at
most one completion per active attempt. Availability excludes stuckness, so the
run ends in matching successful retirement or a matching first fault. N=0 gives
empty successful observations directly. QED.

**Conservative extension.** Empty exports and exclusively retired carried reads
recover the old target and its obligations. Inserting an empty export phase
between completion and retirement does not change their relative order. The old
checker format accepts the absent export field. Existing semantic and F1 tests
are preserved rather than replaced.

**Strict separation family.** Let s_i=s_(i-1)+x_i have unit latency, issue zero,
and a ready unconditional operation ticket at one. Let a separate division tail
have latency L and the fixed skeleton retire at C=L+1. Set input releases zero
and capacities sufficient for both operations and joins. A retired distance-one
read at issue zero requires I>=C. An export of s at F=1 makes I=1 legal without
publishing either s or the tail's fault before retirement. The ordinary recurrence
therefore continues privately while unrelated older work is unfinished. This is
a strict separation between these two certificate interfaces, not a speedup over
an optimal conventional compiler. Exact tail/join costs are fixed by the example.

## 3. Forwarding-bank envelope

Each exported source has a separate uniform ring; label i occupies cell i mod B.
A tag is checked on every read. Let U_v be its set of satisfiable forward uses,
and L_v=max({F_v} union {s+dI:(s,d) in U_v}). A conservative labelled lifetime is
[iI+F_v,iI+L_v], inclusive at both ends because an export is written before a
same-clock issue reads. This lifetime model reserves an exported label even when
its later use is inactive or execution eventually faults. It counts only private
forwarding cells, not local ticket buffers, committed history, inputs or control.

**Theorem B (uniform-ring size).** The least uniform B that preserves every
labelled reservation is floor((L_v-F_v)/I)+1.

*Proof.* Two distinct labels of the same residue class differ by at least B.
The next same-cell write is (i+B)I+F_v. It is later than the last reserved read
iff BI>L_v-F_v. The least positive integer satisfying this strict inequality is
the stated value. Earlier writes cannot destroy i after its own write. Reads
before the first nonnegative producer use initial values. For necessity, if
BI<=L_v-F_v, the write of i+B occurs at or before the reserved last read of i.
At equality, write-before-read priority overwrites the tag first. The labelled
reservation cannot be maintained. This is an envelope witness, not a promise
that this read is reached on every actual program input. QED.

For a fixed set of forward uses, increasing F_v while meeting their deadlines
only decreases the required size. If earliest causal E_v is feasible, the latest
feasible F_v=min(C,min_{u in U_v}(s_u+d_u I)) is also feasible by U1 and minimizes
this separate bank. Choosing earliest F minimizes availability time, not storage.
The selected attempt may change at later times, but X always denotes the same
D(i,v), so a later correct choice cannot invalidate consumers.

**Fault-truncation boundary.** Put an unconditional defined fault first in source
order, C=2, and a later source identity with a distance-64 forward use. All
actual executions stop at the first retirement, before any nonnegative
iteration-64 carried read can occur. A labelled bank requirement of 64 does not
prove that actual terminating executions need 64 cells. The retained control
runs a long requested trip count with one cell and preserves the same early
fault. Global storage optimization would need reachability, liveness, sharing
and fault-aware reclamation, none of which is asserted by Theorem B.

## 4. Exact annotation and export-time normal form

At fixed I, a carried occurrence u=(v,d,s) has deadline D_u=s+dI. Define
M_v(I)={u of v:satisfiable use and D_u<C}. Every occurrence in M is mandatory
forwarding; every remaining active occurrence can read retirement instead.
Permanently inactive occurrences may also remain retired. For nonempty M_v let
U_v=min_{u in M_v}D_u and L_v=max_{u in M_v}D_u. Now U_v<C and L_v>=U_v.

**Theorem H (canonical hybrid optimum).** Over every annotation of the fixed
skeleton that changes each carried reference only between retired and forward,
and over every causal Boolean-only export partition/time, the minimum number
of separate uniform forwarding cells is

  sum over v with M_v nonempty of (floor((L_v-U_v)/I)+1),

provided each such source admits a selector at U_v and the common resource
obligations hold. If one required selector does not exist, no annotation in this
class is admitted. If resources fail, changing annotations cannot repair them.
A minimum is constructed by forwarding exactly M, dropping unused exports, and
exporting each needed source at U_v.

*Proof.* A retired occurrence requires C<=D_u. Thus every member of M must be
forwarded in any admitted annotation. An optional forward occurrence has
D_u>=C; replacing it by retired is legal. Its source identity is unchanged and
both reference forms provide goodness true. Hence all locally derived gamma,
activation masks, retirement choices and reservations are unchanged. Removing
an optional forward use only relaxes export deadline constraints and reduces
or preserves the largest forward-read time. If a source has no mandatory use,
remove all its optional uses and export, saving its nonnegative bank cost.
For a remaining source, every legal annotation has export time F<=U_v. If no
selector exists at U_v, monotonicity implies none exists at any earlier F; this
contradicts admission. If one exists, select it at U_v. Keeping exactly mandatory
uses makes the last lifetime endpoint L_v. Any alternative legal annotation has
F'<=U_v and L'_v>=L_v (possibly with added optional uses). Its lifetime length
L'_v-F'>=L_v-U_v, so Theorem B makes its integer cell count no smaller. Sources
have separate banks, so these lower bounds add and the canonical construction
attains their sum. Check all unchanged non-carried obligations and the common
resource envelope to conclude admission. QED.

This proof does not require a monotone cell-count function of I. Mandatory sets
change with I, and intermediate floor expressions need not support binary
search. It does not optimize operation placement, primitive costs, source
rewrites, ordinary-value tests, value-dependent export times, bank coalescing,
register spilling, or partial source retirement. These choices are fixed or
outside the search class.

**Theorem C (finite period cutoff).** Under the skeleton premises, the unbounded
mathematical period/cell Pareto set is obtained by testing integers
1..max(1,C). For I>=C, no active carried occurrence is mandatory, canonical
forwarding storage is zero, and resource admission is constant across such I.

*Proof.* Positive distance and nonnegative issue give s+dI>=I>=C. Thus every
carried read can be retired. Every active reservation offset s+delta is strictly
less than s+ell<=C, so lies in [0,C). For I>=C all active reservation records are
in stage zero, with phase equal to their unchanged offset. No records from
different offsets alias; same-offset records retain exactly their local
predicate maximum. The resource criterion is therefore the same as at I=C.
Local, input, goodness and retirement obligations do not change with I. All
points with I>C have zero cells and the same admission as C, so C dominates
them. If C=0, positive-latency active producers cannot satisfy a nonempty
retirement partition; the convention max(1,C) also handles this degenerate
empty-feasible case. QED.

The implementation's period cap is 256. When C>256, it explicitly reports that
its enumerated Pareto set is not complete for unbounded periods. The theorem
is about the language, not an assertion that a bounded checker accepts larger
integers. A bank budget is solved by selecting the least admitted period whose
canonical cell sum fits; a larger period must not be presumed resource-feasible
without checking it. Zero budget recovers the retirement-only alternative in
the canonical search, rather than excluding it as all-forward synthesis does.

## 5. Resource envelope and a startup realization lemma

For each resource r, write s_a+delta=kI+phi for every reservation record. At
clock qI+phi its iteration is q-k. Let W_(r,phi,k)(theta) count active records in
that phase/stage bucket. The established activation-envelope peak is
P_(r,phi)=sum_k max_theta W_(r,phi,k)(theta). Upper boundedness follows by grouping
records by their actual iteration. Tightness for independent activation streams
chooses maximizing valuations separately for each stage. Fixed finite inputs or
correlated predicates can restrict that maximization.

**Theorem R (startup realization for this complete-by-C language).** If all
non-resource obligations hold, every positive component P_(r,phi) is realized
in some actual abstract run before its first retirement. Consequently capacity
bounds are necessary and sufficient for all finite trip counts and all admitted
ordinary-input/independent-Boolean streams, within this abstract reservation model.

*Proof.* Ignore zero-peak stages; let K be the largest remaining stage. Its
positive contribution contains an active reservation at offset KI+phi<C by
complete-by-C and delta<ell. Choose N=K+1 and clock T=KI+phi. Give iteration K-k
a maximizing valuation of bucket k. Indices are distinct and in [0,N); arbitrary
unused iterations/atoms can be filled. Every contributing reservation belongs
to its intended iteration and occurs at T. Availability and preservation's
private-event argument ensure all scheduled active computations up to T can
issue. Any defined primitive error remains private: T<C, while C is the first
retirement time. Thus no error has terminated this run, and every counted
reservation is present. The count equals P, including for a run that faults
at C immediately afterward. Well-formed ordinary input values and initial
values can be chosen arbitrarily; lifted errors do not block private attempts.
The usual envelope upper bound proves sufficiency. The startup witness proves
necessity whenever a capacity is below a positive P. QED.

Quantifiers matter. This is an existential sufficiently long startup witness
for a universally quantified certificate class. It does not say that a chosen
short trip count, a particular Boolean stream or a fault-truncated steady-state
trace realizes P. Nor does it make the forwarding-bank envelope exact for
actual executions: its largest read may occur many periods after C, outside the
startup argument. Removing complete-by-C or adding speculative control
cancellation invalidates the proof and requires a new resource analysis.

## Implementation correspondence and finite checks

`checker.py` derives gamma, checks export partitions, identities and readiness,
and compares carried deadlines. `frontiers.py` implements information cells,
earliest selectors, replayable obstructions, fixed-all-forward synthesis,
canonical hybrid annotation, bank arithmetic, complete cutoff enumeration and
startup witness construction. The untrusted synthesis output is always sent to
`check`. `target.py` implements the four event priorities and an optional tagged
ring. `reference.py` is unchanged. `frontier_oracle.py` separately enumerates
whole selector tables, explicit ring events, all small annotations/export-time
tuples, and direct integer-clock target execution; it imports no checker,
frontier synthesizer, or target implementation. Separation of implementations
is not independent provenance.

The finite selectors include all two-atom/two-ticket goodness masks under their
registered completion/release domains. The annotation oracle enumerates every
Ret/Forward choice and every export time for four bounded skeletons and all
registered periods. Startup tests count actual issued reservations, including
capacity-violating witnesses; they do not merely compare two formulas. The
fault-bank control refutes an overstrong reachable-storage interpretation.
Counters, cases and measured execution records are in `results/frontier-*.json`
and `cases/frontiers/`. They must be regenerated by `reproduce.py` to count as a
fresh scientific run; reading old result files or running a reconciler alone
is not a new experiment.
