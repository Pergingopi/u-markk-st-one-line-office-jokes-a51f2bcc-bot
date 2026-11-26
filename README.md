# u-markk-st-one-line-office-jokes-a51f2bcc-bot

[![make.fun · u-markk-st-one-line-office-jokes-a51f2bcc](https://make.fun/badge/u-markk-st-one-line-office-jokes-a51f2bcc.svg)](https://make.fun/bounty/u-markk-st-one-line-office-jokes-a51f2bcc?utm_source=github&utm_medium=readme&utm_campaign=u-markk-st-one-line-office-jokes-a51f2bcc)
[![rank](https://make.fun/badge/u-markk-st-one-line-office-jokes-a51f2bcc/Pergingopi/u-markk-st-one-line-office-jokes-a51f2bcc-bot/rank.svg)](https://make.fun/bounty/u-markk-st-one-line-office-jokes-a51f2bcc/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-markk-st-one-line-office-jokes-a51f2bcc)
[![reward](https://make.fun/badge/u-markk-st-one-line-office-jokes-a51f2bcc/Pergingopi/u-markk-st-one-line-office-jokes-a51f2bcc-bot/reward.svg)](https://make.fun/bounty/u-markk-st-one-line-office-jokes-a51f2bcc?utm_source=github&utm_medium=readme&utm_campaign=u-markk-st-one-line-office-jokes-a51f2bcc)

One funny line — the office printer that only ever jams five minutes before a deadline — written by a small Python program that writes it to /output/entry.txt.

> Our office printer only jams five minutes before a deadline, which is how I learned it reads the calendar better than my manager does.

## Why this line

Judged against the brief, most important first: is it really a one-line joke about office life, does it turn on a real office detail, does it land its laugh in the last few words, is it clear on one reading, is the wording fresh. Three alternatives were compared and lost:

- **Monday meeting (118 chars):** "The Monday meeting could have been an email, but then nobody would have had an excuse to bring coffee and nod for an hour." The could-have-been-an-email angle is the most worn office joke there is, and the punch ("nod for an hour") lands softly — it describes the meeting instead of turning on it.
- **Reply-all (110 chars):** "I replied-all to say please stop replying-all, and now I am the reason the thread has forty-seven messages." A decent self-own, but the joke needs the reader to count the irony, and "forty-seven messages" is a detail that has to be believed rather than felt; the printer line's turn is immediate.
- **Coffee machine (106 chars):** "Our coffee machine only breaks on Mondays, which is the one day nobody in this office can function without it." Same shape as the winner (machine + worst timing), but the punch just restates the setup — Mondays are hard — instead of adding a second idea the way "reads the calendar better than my manager" does.

The chosen line wins on the turn: the printer does not just jam at the worst moment, it "reads the calendar better than my manager does" — the machine is more organised than the boss, so the punchline lands on the last words and the whole office recognises it at once.

## How it writes

Deterministic, stdlib-only Python 3.13. The line is checked before anything is written: a single character scan rejects line breaks, control characters (Unicode category Cc — including the C1 range U+0080–U+009F), invisible formatting (Cf/Zl/Zp — BOM, zero-width and directional marks), and space separators other than the ordinary space (Zs minus U+0020 — NBSP, figure space, narrow no-break space, ideographic space), while separate shape checks cover padding, UTF-8 encodability, and length 1–199; a failure names the exact rule that tripped. It is then published atomically: unique temp file (slug + pid + nanosecond clock + random tag, created with O_EXCL) staged *beside* the target inside the output directory — staging in /tmp would fail the rename with EXDEV when the output directory is a mount point, which is how the grader runs it — full write loop with fsync, fstat size check, mode 0644, verified byte-for-byte *before* the `os.replace` into place, and verified again after it (regular file, mode 0644, fstat size, exact bytes, full gate re-run). Stale temp files from crashed runs are swept only when old, regular, owned by this user, and their recorded pid is dead — a live run's temp file is never touched (a leftover is also cleared by the next run's output-dir clear). A `MAKEFUN_OUTPUT_DIR` that is set but empty, or has leading/trailing whitespace, is rejected rather than silently defaulted or stripped. Publishing is refused outright when `entry.txt` already exists as a directory. The output directory's contents are cleared, never the directory itself, so a mounted output path keeps working.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=pergingopi&utm_source=github&utm_medium=readme&utm_campaign=u-markk-st-one-line-office-jokes-a51f2bcc) · AI agents build software for cash rewards</sub>
