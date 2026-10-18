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
| Mass-sell (QoL) binary patch | `tools/patch_mass_sell.py`, `tools/assemble_hook.py`, `tools/find_code_cave.py` |
| Patch verification (disassembly-level) | `tools/verify_patch.py` |
| Tests | `tests/` (`python3 -m unittest discover tests`) |
| RE findings | `CLAUDE.md`, `docs/` |

## No copyrighted content

Only tooling, notes, and small factual excerpts (offsets, opcodes, table layouts)
are published. The actual `6RAH.APP` executable, `*.dat` data files, `*.MBM`
bitmaps, and audio are **not** included and will never be. If you want to use
these tools, supply your own legally obtained copy of the game.

## Usage

Requirements: Python 3 + [`capstone`](https://pypi.org/project/capstone/).

```bash
pip install capstone

# 1. Back up your install first (both patchers also create .orig backups).
# 2. Make every combine recipe 100% (patches the live itemdata.dat tails):
python3 tools/patch_100_percent_combine.py

# 3. Add mass-sell to the executable:
python3 tools/patch_mass_sell.py <path-to>/6RAH.APP
python3 tools/verify_patch.py

# 4. Run the tests:
PYTHONPATH=. python3 -m unittest discover tests
```

Both patchers are idempotent and back up any file before touching it.

Tools default to `System/Apps/6RAH` relative to your working directory. Point
them (and the tests) at your own install with:

```bash
export PK_GAME_DIR="/path/to/your/System/Apps/6RAH"
```

Tests skip themselves cleanly when no game install is found.

## Findings in one screen

- The game **never opens `comp*.dat`** — those are editor exports. The live recipe
  tables are the 4704-byte tail of `itemdata.dat` (and `english/itemdata.dat`).
- Recipes are 16-byte entries starting at tail-relative +32; the per-recipe
  success rate is the byte at `entry + 6`. The table header's base rate is at
  `header + 22`.
- Vanilla rates ranged from 5% to 90% (80 cells sat at 30% or below). All 217
  rate cells are documented, and the patcher raises every one to 100%.
- Mass-sell is a 25-byte binary change hooking the shop's sell page.

Details, offsets, and honest status of open questions: see `CLAUDE.md`.
