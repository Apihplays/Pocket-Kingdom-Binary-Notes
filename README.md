# Pocket-Kingdom-Binary-Notes

Reverse-engineering notes, patch tooling, and tests for the Nokia N-Gage game
**Pocket Kingdom: Own the World** (Symbian OS 6.1/7.0s, ARMv4T, E32Image).

This repository is a **toolkit + research log**, not a distribution. It contains
**no game binaries, no extracted game data files, and no artwork**. The scripts
here patch a copy of the game that *you* already own. The unit/emblem database
under `unitdb/` is factual game statistics transcribed from a 2005 fan site
(pk.warcry.com) — not game assets.

## What's here

| Area | Files |
|---|---|
| 100% combine/merge success rates | `tools/patch_100_percent_combine.py` |
| Unit & emblem database + offline app | `tools/build_unitdb.py`, `unitdb/` |
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

## Unit & emblem database

**Live app: <https://apihplays.github.io/Pocket-Kingdom-Binary-Notes/>**

`unitdb/` is a compact offline database built from archived pk.warcry.com pages
(Wayback Machine, 2005): 115 units (class, race, rank, slots, move,
HP/ATK/DEF/AGI/DEX/WIS/INT/HIT%), their special abilities, the full evolution
tree (target, rank, level, VP, RankUp Emblem), and 31 emblems / 70 recipes.

`unitdb/PocketKingdom-Units.html` is a **self-contained app** — open it in any
browser; no server or internet needed. It has:

- **Units** — filter by race / move / slots / rank, sort any stat, see the best
  value for the current result set, and open a unit for its ability + evolution.
- **Team Builder** — add units, set a slot cap, and watch total slots and
  combined stats (saved in your browser).
- **Emblems** — recipe table (Ore + Item1 + Item2 → Success%); clicking a
  RankUp Emblem in a unit's evolution jumps straight to its recipe.

Rebuild/refresh:

```bash
python3 tools/build_unitdb.py --details --emblems
```

`--details` re-fetches each unit page and `--emblems` the recipe table; both
cache into `unitdb/raw/` (git-ignored). Omit the flags for a fast index-only
rebuild. Stats are base values — the game scales them with level, and
combining/evolving changes them.

## Removed: mass-sell

An earlier mass-sell (`6RAH.APP`) patch was removed. It passed byte-level checks
but never worked in game — it altered the wrong sell loop and never credited gold.
`6RAH.APP` is kept vanilla; the removed code is recoverable from git history.

## No copyrighted content

Only tooling, notes, and small factual excerpts (offsets, opcodes, table layouts)
are published. The actual `6RAH.APP` executable, `*.dat` data files, `*.MBM`
bitmaps, and audio are **not** included and will never be. If you want to use
these tools, supply your own legally obtained copy of the game.
