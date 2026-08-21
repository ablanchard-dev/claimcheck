# claimcheck

Checks what a coding agent **says it did** against what the turn actually shows it did.

The failure this targets is not "the AI writes bad code". It is: the agent writes *"tests
green"*, *"file created"*, *"pushed"* because that is the expected **shape** of a finished
task — not because it looked. Published measurements put GPT-5 at submitting a patch 100% of
the time while resolving 44% of tasks, and developers report spending roughly a quarter of
their week checking AI output.

claimcheck runs as a Claude Code `Stop` hook. It reads the agent's final message, finds the
claims it recognises, and confronts each one with the tool output produced in that same turn.
It blocks only when a claim is contradicted.

## What it will not do

**It never re-runs anything.** Re-running a test suite at every turn end costs tens of seconds
(88 s measured on a real repository) and the hook gets uninstalled within a day. It checks that
the command *actually ran*, by looking for the tool result that backs the claim. That is free,
deterministic, and it targets the real defect: announcing without having run.

**It never returns a score.** Benchmarks show a model asked to rate output assigns the same
average score to everything. There is no judgement here — a claim is contradicted by an output
or it is not, and the raw output is attached.

**It has three states, never two.** `verified`, `refuted`, `unverifiable`. "I could not look" is
not "this is false". A tool that merges them accuses wrongly, and its own failure mode becomes
the one it exists to prevent.

**It never refutes a claim whose referent is undetermined.** "0 fail" — of which runner? "8
commits pushed" — a single push carries eight. When the sentence cannot be pinned to a specific
piece of evidence, the answer is `unverifiable`. Refuting requires knowing what the sentence
points at.

**It never judges an intention.** "push the 9 repos" is a plan; "9 repos pushed" is a report.
Only the second asserts anything about the past.

## The ceiling, stated up front

claimcheck verifies **only** claims whose evidence was produced in the turn. Not narration, not
citations, not durations, not anything checked elsewhere. Every run prints how much it looked at:

```
COUVERTURE
  phrases chiffrées trouvées        : 27
  dont vérifiables depuis ce tour   : 15
  dont effectivement reconnues      : 10   (67% du vérifiable, 37% du total)
  -> 5 affirmation(s) vérifiable(s) N'ONT PAS ÉTÉ REGARDÉES.
  -> 12 hors portée par construction (narration, citations, durées).
  « 0 réfuté » ne veut pas dire « tout est vrai ».
```

Both denominators are printed, and the wider one is never dropped in favour of the flattering
one. A verification tool that reports "0 refuted" without saying how much it examined reads as a
green light when it means "I looked at a third".

The coverage metric is deliberately **conservative**: it counts a few sentences as in-scope that
are not really checkable, so the reported figure understates real coverage. For a tool of this
kind that is the correct direction to be wrong in.

## Measured

| Bench | Result |
|---|---|
| Mutation proof (`test_mutation.py`) | 12/12 |
| Hook, real JSON on stdin | 5/5 |
| False positives on a real session transcript | 0 |
| Hostile conditions (`test_robustesse.py`) | 17/17 |
| Hook cost on a 4000-output transcript | 0.10 s |
| Coverage | 67% of what is checkable, 37% of all numeric sentences |

`check_all.py` re-derives every figure in that table and fails if the README has
drifted. The turn count was deliberately dropped from it: the transcript keeps
growing, so a fixed count went stale within the hour — the bench caught it.

The mutation proof exists because the tool found nothing on healthy data. A detector that
detects nothing on its only corpus is not proven, it is untested — you have to fabricate the
false claim to test the detector of false claims. Both real defects it caught were **unit
errors**: counting tool outputs instead of pushes, then counting pattern occurrences instead of
ref-update lines. Neither was visible on re-reading.

## Usage

```
python claimcheck.py <transcript.jsonl>   # audit a whole session
python claimcheck.py --hook               # Stop hook, JSON on stdin
```

Hook mode reads `last_assistant_message` and `transcript_path`, and emits
`{"decision": "block", "reason": ...}` when a claim is contradicted. Nothing otherwise.

Requires Python 3.8+. No dependencies.

**It never crashes and never blocks on degraded input.** Missing transcript, empty
file, invalid JSON, malformed stdin, absent message, accented path: every one of
those is a silence, not an error and not an accusation. A hook that throws at every
turn end is uninstalled the same day, and then nothing is checked at all.

## Known limits

- Recognises four claim shapes: test counts, `0 fail`, pushed-repo counts, commit SHAs.
- French and English phrasing, tested on French transcripts.
- Claim extraction is pattern-based, so an unusual phrasing is simply not seen — and that
  silence is counted in the coverage line rather than hidden.
