# Pocket Kingdom: 100% Combine Rates (N-Gage / EKA2L1)

Patches every recipe/combine success rate in *Pocket Kingdom: Own the World* to **100%**, so no combine ever fails.

## What it changes
- **Live recipe tables** — the 4704-byte tail of `System/Apps/6RAH/itemdata.dat` and
  `System/Apps/6RAH/english/itemdata.dat`. This is the data the game actually loads at runtime.
- **Dev copies** — every `comp*.dat` table, for consistency (the retail game never opens these).
- Per-recipe rate (byte at `entry+6` of each 16-byte recipe entry) and the table header
  rate (byte at `+22`) are both set to `0x64` (100).

## Requirements
- Python 3
- The game install. Defaults to `System/Apps/6RAH`; pass a path or set `PK_GAME_DIR` for another copy.

## Usage
```bash
python3 tools/patch_100_percent_combine.py
# or target a specific install:
python3 tools/patch_100_percent_combine.py "/mnt/c/Users/<you>/Downloads/Pocket Kingdom/System/Apps/6RAH"
```

- Idempotent: a second run makes zero changes.
- `itemdata.dat` / `english/itemdata.dat` get a one-time `.orig` backup; `comp*.dat` are patched in place.

## Verify
```bash
PYTHONPATH=. python3 -m unittest discover tests
```
Tests self-skip when no game install is present; point them at one with `PK_GAME_DIR`.

## Binary notes
See `CLAUDE.md` for the reverse-engineered offsets and how the rates are located/loaded.

## History
An earlier **mass-sell** patch (`6RAH.APP` hook) was removed — it never worked in game: it
altered the wrong sell loop and never credited gold. `6RAH.APP` is kept vanilla; only the
recipe data is modified. The removed code remains in git history.
