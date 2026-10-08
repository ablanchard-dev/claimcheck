# Manual install (without the plugin), and how to remove it

The plugin install in the README is the simple path. This page is for wiring the hook by
hand in `settings.json`. A `Stop` hook runs on **every** session, so removal comes first.

## 1. Removal

Open `~/.claude/settings.json` (`%USERPROFILE%\.claude\settings.json` on Windows) and
delete the block that contains `claimcheck.py` under `hooks.Stop`. Nothing else is changed
on the machine: no service, no scheduled task, no registry key.

To switch it off without editing JSON, rename the `claimcheck` folder. The command fails,
the hook returns nothing, and Claude Code carries on normally (see section 4).

## 2. The block to add

Under `hooks.Stop`, **in addition** to what is already there (the array takes several
entries):

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "python3 /path/to/claimcheck/claimcheck.py --hook"
    }
  ]
}
```

On Windows, use `py "C:\\path\\to\\claimcheck\\claimcheck.py" --hook`. The `py` launcher
does not depend on whichever virtualenv `python` happens to resolve to; if that venv
disappears, a hook using `python` dies silently and nothing gets checked.

## 3. Check it is wired, without waiting for a block

If the hook is wired wrong, you will never see anything and will assume it is watching.
Force the case from the claimcheck folder. `exemple-tour.jsonl` is a minimal real turn in
which pytest printed `162 passed`:

```
echo '{"last_assistant_message":"I ran it: 170 tests passed.","transcript_path":"exemple-tour.jsonl"}' | python3 claimcheck.py --hook
```

A `{"decision": "block", ...}` line means the hook works. With `162 tests passed` (the
truth), nothing is printed. The transcript must contain a runner output: without evidence
the hook never blocks, on purpose.

The full bench: `python3 check_all.py` (expected: exit code 0).

## 4. What happens on a block

The agent ends its turn, the hook finds a claim **contradicted by a tool output of the same
turn**, and prevents the stop. The agent continues with the claim, the output against it,
and what to do.

It never blocks on:

- an intention ("I'll push the 9 repos") — a plan, not a report;
- a claim with no evidence in the turn — "I could not look" is not "this is false";
- a claim whose referent is undetermined ("0 failures" when several runners ran and some
  failed on purpose, as in mutation testing);
- degraded input: missing transcript, broken JSON, empty stdin, accented path. All of these
  are a silence. A hook that crashes at every turn end is uninstalled the same day.

The hook re-runs nothing: it looks for evidence already produced. Cost: about 0.1 s.

## 5. If a block looks wrong

That is the worst defect this tool can have, so please report it: the block message always
contains the claim and the opposing output, which is enough to judge. Add the case to
`test_mutation.py` as a witness (it must pass), then fix.
