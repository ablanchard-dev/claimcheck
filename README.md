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

**It never refutes on missing evidence.** A test count is refuted only by a *competing value*:
a count the runner itself printed (`162 passed`, `235 PASS`, `réussite : 8`) that differs from
the claim. No count in the turn means "no evidence here", never "false". Several runners with
different counts means the referent is undetermined, unless their sum matches the claim. Earlier
turns of the session can confirm a number, never refute it. The earlier rule refuted on absence;
over 1,277 real turns that produced 14 refutations and none of them caught a real error.

## What it blocks besides numbers

"It's fixed", "ça marche", "bug corrigé" after a **code** file was edited in the turn and
**no command ran after the last edit**. This is read from the sequence of tool calls, not from
the wording of numbers. Documentation and config edits (`.md`, `.json`, ...) are exempt, since
they have no test to run. Any command after the edit counts as execution. That is a deliberate
ceiling: it can miss a "fixed" followed only by `ls`, but it never accuses an agent that ran
something. Over 2,779 real turns there were 51 such announcements, all followed by a real run.
So the rule blocked nothing there, and mutation tests confirm that it does fire.

## The ceiling, stated up front

claimcheck verifies **only** claims whose evidence was produced in the turn. Not narration, not
citations, not durations, not anything checked elsewhere. Every run prints how much it looked at:

```
COUVERTURE
  phrases chiffrées trouvées        : 95
  dont vérifiables depuis ce tour   : 94
  dont effectivement reconnues      : 12   (13% du vérifiable, 13% du total)
  -> 82 affirmation(s) vérifiable(s) N'ONT PAS ÉTÉ REGARDÉES.
  -> 1 hors portée par construction (narration, citations, durées).
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
| Mutation proof (`test_mutation.py`) | 33/33 |
| Hook, real JSON on stdin | 5/5 |
| False positives on two real sessions (1,277 turns) | 0 (was 14) |
| Hostile conditions (`test_robustesse.py`) | 17/17 |
| Hook cost on a 4000-output transcript | 0.10 s |
| Hook cost on a 111 MB transcript | 0.66 s |
| Coverage | printed at every run, on both denominators |

`check_all.py` re-derives every figure in that table and fails if the README has
drifted. Two figures were deliberately dropped from it — the turn count and the
coverage percentage: both depend on a transcript that keeps growing, and both went
stale within the hour. The bench caught them. A number nobody can keep true is not
information, it is a trap; the tool prints the live one instead.

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
