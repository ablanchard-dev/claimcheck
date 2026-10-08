# claimcheck

Checks what a coding agent **says it did** against what the turn actually shows it did.

The failure this targets is not "the AI writes bad code". It is: the agent writes *"tests
green"*, *"file created"*, *"pushed"* because that is the expected **shape** of a finished
task — not because it looked. "GPT-5 submits a patch on 100% of runs but resolves only 44%"
(Mehta, *Confident and Wrong: Silent Semantic Failures in Coding Agents*, arXiv 2603.25764,
March 2026).

claimcheck runs as a Claude Code `Stop` hook. It reads the agent's final message, finds the
claims it recognises, and confronts each one with the tool output produced in that same turn.
It blocks only when a claim is contradicted.

## Quick start

Needs Python 3.8+ (`py` on Windows, `python3` elsewhere). No dependencies.

**Install** (two commands, in a terminal):

```
claude plugin marketplace add ablanchard-dev/claimcheck
claude plugin install claimcheck@claimcheck
```

Or from inside Claude Code: `/plugin marketplace add ablanchard-dev/claimcheck`, then
`/plugin install claimcheck@claimcheck`. Restart the session. Nothing else to configure.

**See it work** (from the cloned folder). `exemple-tour.jsonl` is a turn where pytest printed
`162 passed`:

```
echo '{"last_assistant_message":"I ran it: 170 tests passed.","transcript_path":"exemple-tour.jsonl"}' | python3 claimcheck.py --hook
```

It prints `{"decision": "block", ...}`. With `162 tests passed` it prints nothing.

**Remove:** `claude plugin uninstall claimcheck@claimcheck`

**Run the tests:** `python3 check_all.py` (on Windows: `py check_all.py`).

What you will see in a session: when the agent ends a turn on a claim its own output
contradicts, it does not stop. It gets the claim, the output against it, and what to do
("run the tests, then rewrite the report from their output"), and carries on.

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

"Fixed", "it works now", "c'est corrigé" after a **code** file was edited in the turn and
**no command ran after the last edit**. This is read from the sequence of tool calls, not from
the wording of numbers. Documentation and config edits (`.md`, `.json`, ...) are exempt, since
they have no test to run. Any command after the edit counts as execution. That is a deliberate
ceiling: it can miss a "fixed" followed only by `ls`, but it never accuses an agent that ran
something. Over 2,779 real turns there were 51 such announcements, all followed by a real run.
So the rule blocked nothing there, and mutation tests confirm that it does fire.

A fix reported together with a first-person "I haven't compiled / tested" is a stated limit,
not a false success, and passes. The admission has to be about this turn and name compiling or
testing: "the old module was not tested" or a vaguer "nothing run" still blocks, which is what
keeps the deliberate live probe blocked.

For "0 failures", the **last** test summary of the turn decides. A deliberate mutation that
fails and is followed by a clean full run no longer refutes a true claim; a clean run followed
by a failing one, or a `fail = 0` read in source code, proves nothing.

"I reviewed all 12 files", "j'ai relu les fichiers" in a turn where **no tool other than
an edit ran**: no read, no search, no command, no subagent. Agents announcing a complete
review they did not do is the most frequent overclaim measured by OverclaimBench (arXiv
2609.20812, September 2026). The rule does not count files, so any reading at all lets the
claim through; it only catches a review announced with nothing read.

"132 commits ahead", "3 commits d'avance" is compared with what `git status` printed in the
turn (`[ahead 132]`, or the English and French long forms). Several repositories with
different counts leave the claim unverifiable.

## The ceiling, stated up front

claimcheck verifies **only** claims whose evidence was produced in the turn. Not narration, not
citations, not durations, not anything checked elsewhere. Every run prints how much it looked at:

```
COVERAGE
  sentences with a number          : 95
  of which checkable from the turn : 94
  of which actually recognised     : 12   (13% of checkable, 13% of total)
  -> 82 checkable claim(s) were NOT LOOKED AT.
  -> 1 out of scope by design (narration, citations,
     durations: their evidence does not live in this turn).
  "0 refuted" does not mean "everything is true".
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
| Mutation proof (`test_mutation.py`) | 93/93 |
| Hook, real JSON on stdin | 16/16 |
| False positives on two real sessions (1,277 turns, 2026-09-23) | 0 (was 14) |
| False positives on all local sessions (378 files, 3,952 turns, 2026-09-23) | 0 (was 8 after the first fix) |
| Same, with subagent transcripts (592 files, 4,235 turns, 2026-09-23) | 0 false alarms, 1 true positive: a deliberate probe that the **installed** hook blocked in a live session |
| Same, two weeks later (590 files, 8,294 turns, 2026-10-06) | 0 false alarms (was 2: a fix reported *with* "nothing compiled or tested", and a true "0 failures" printed by a script after a deliberate mutation), the probe still blocked |
| Same, after adding English forms and JS runners (567 files, 8,685 turns, 2026-10-08) | 0 false alarms (2 found during the change and fixed: a French `somme 4848 echecs` total and a `uniq -c` count of `Failed` log lines, both read as failures), the probe still blocked |
| Same, after adding commits-ahead, `N/N` forms and the review rule (570 files, 8,707 turns, 2026-10-08) | 0 false alarms; the review rule fired on no real turn, the probe still blocked |
| Hostile conditions (`test_robustesse.py`) | 17/17 |
| Hook cost on a 4000-output transcript | 0.10 s |
| Hook cost on a 111 MB transcript | 0.17 s (reads the last 8 MB; same verdict as a full read on all 384 local sessions, 2026-09-23) |
| Hook cost on a 500 MB transcript | 0.14 s (2026-10-06; tail read still matches the full read on all 31 sessions larger than 8 MB) |
| Coverage | printed at every run, on both denominators |

The corpus rows are re-measured by `python3 corpus.py`, which replays the tool on every
local session, checks that the 8 MB tail read gives the same verdict as a full read, and
exits 1 on any refutation. Run on the code as it stood before the fixes of 2026-09-23, it
finds the 8 false alarms and exits 1, so a clean run means something.

`check_all.py` re-derives every other figure in that table and fails if the README has
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
python3 claimcheck.py <transcript.jsonl>   # audit a whole session (py on Windows)
python3 claimcheck.py --hook               # Stop hook, JSON on stdin
```

Hook mode reads `last_assistant_message` and `transcript_path`, and emits
`{"decision": "block", "reason": ...}` when a claim is contradicted. Nothing otherwise.

Requires Python 3.8+. No dependencies.

**It never crashes and never blocks on degraded input.** Missing transcript, empty
file, invalid JSON, malformed stdin, absent message, accented path: every one of
those is a silence, not an error and not an accusation. A hook that throws at every
turn end is uninstalled the same day, and then nothing is checked at all.

## Known limits

- Recognises seven claim shapes: test counts, `0 fail`, pushed-repo counts, commits ahead,
  commit SHAs, "fixed" after a code edit, and a review announced with nothing read.
- Reads runner counts from pytest, cargo, dotnet, jest, vitest and mocha output. `go test`
  prints no count, so a count claimed against it stays unverifiable.
- A single runner in the turn contradicts a test count only within a factor of 2. Beyond
  that it may be a different suite (measured: one project's total of 4,537 against a 629-test
  run of another project), so a gross fabrication against a suite of another size is reported as unverifiable.
- `0 fail` is refuted only when the turn has exactly one runner. With several, some failing
  on purpose (mutation testing), the referent is undetermined.
- French and English phrasing. The real-session corpus is French, so English forms are
  covered by witness and mutation tests only: their false-alarm rate is less measured.
- Claim extraction is pattern-based, so an unusual phrasing is simply not seen — and that
  silence is counted in the coverage line rather than hidden.

## License

GPL-3.0. See `LICENSE`.
