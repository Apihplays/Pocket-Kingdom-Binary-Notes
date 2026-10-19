# Pocket-Kingdom-Binary-Notes

Reverse-engineering notes, patch tooling, and tests for the Nokia N-Gage game
**Pocket Kingdom: Own the World** (Symbian OS 6.1/7.0s, ARMv4T, E32Image).

This repository is a **toolkit + research log**, not a distribution. It contains
**no game binaries, no game data files, and no artwork**. The scripts here patch
a copy of the game that *you* already own.

## What's here

| Area | Files |
|---|---|
| 100% combine/merge success rates | `tools/patch_100_percent_combine.py` |
| E32Image → ELF wrapper (for REA/Hopper analysis) | `tools/wrap_raw_arm_elf.py` |
| Tests | `tests/` (`python3 -m unittest discover tests`) |
| RE findings | `CLAUDE.md`, `docs/` |

## 100% combine rates

Patches every recipe/combine success rate to 100% in the live tables — the
4704-byte tail of `itemdata.dat` and `english/itemdata.dat` (per-recipe byte at
`entry+6`, table header byte at `+22`) — plus the standalone `comp*.dat` dev
copies for consistency. The retail game never opens `comp*.dat`; see `CLAUDE.md`.

```bash
python3 tools/patch_100_percent_combine.py [app_dir]
# app_dir defaults to System/Apps/6RAH, or set PK_GAME_DIR
```

Idempotent; creates one-time `.orig` backups for `itemdata.dat`. Tests self-skip
when no game install is present.

## Removed: mass-sell

An earlier mass-sell (`6RAH.APP`) patch was removed. It passed byte-level checks
but never worked in game — it altered the wrong sell loop and never credited gold.
`6RAH.APP` is kept vanilla; the removed code is recoverable from git history.

## No copyrighted content

Only tooling, notes, and small factual excerpts (offsets, opcodes, table layouts)
are published. The actual `6RAH.APP` executable, `*.dat` data files, `*.MBM`
bitmaps, and audio are **not** included and will never be. If you want to use
these tools, supply your own legally obtained copy of the game.
