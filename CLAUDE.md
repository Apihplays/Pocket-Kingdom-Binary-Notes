# CLAUDE.md - Reverse Engineering Guidelines & MCP Tools

## Project Overview
This repository contains reverse engineering analysis, tools, and modifications for **Pocket Kingdom: Own the World** (Nokia N-Gage / Symbian OS 6.1/7.0s ARMv4T binary).

## Primary Reverse Engineering Tool: REA (Reverse Engineer Anything)
When reverse engineering, investigating file formats, decompiling, or inspecting binaries in this project:
- Always leverage **`npx rea-agents`** commands (or the REA MCP tools if running in MCP mode):
  - `npx rea-agents inspect-artifact <file>`
  - `npx rea-agents analyze <path>`
  - `npx rea-agents decompile <path>`
  - `npx rea-agents instructions <path>`
  - `npx rea-agents search-bytes <pattern>`
- REA provides static and runtime analysis across native binaries, web bundles, bytecode, and application graphs.
- RE analysis transcripts live in `docs/` (see `docs/comp_loader_points.md`, `docs/superpowers/plans/`).

## Symbian / N-Gage Binary Architecture
- **Main Executable:** `System/Apps/6RAH/6RAH.APP`
  - Format: Symbian E32Image (uncompressed EPOC binary, CPU: 0x2000 / ARMv4T)
  - Code Base: `0x10000000`, Code Offset: `0x7C`
  - Text Section Size: `0xB0CAC` (~724 KB); extracted code segment at repo root: `6rah_code.bin`
    (offset 0 of `6rah_code.bin` = VA `0x10000000`)
  - MultiBitmap Assets: `POKEKIN.MBM` (contains 488 bitmap sprites/UI elements)
  - Data Files: `System/Apps/6RAH/*.dat` and `System/Apps/6RAH/english/*.dat` (english dir = localized text; tails of `itemdata.dat` are identical)
- **Known subroutines (from RE):**
  - `0x1000cc40` recipe-merge/install path; recipes resident at game-struct `M+0x480..0x4a4`, merge pointer `M+0x498` init at `0x10069900`
  - `0x10031428` item-info lookup; `0x10031570-0x1003157c` `[M+0x498]` handling
  - `0x10005E98` sell confirmation handler (mass-sell hook target)
- **Testing Environment:** EKA2L1 Symbian Emulator on Windows host.
  - Windows share path: `\\wsl.localhost\archlinux\home\bossku\Pocket Kingdom\System\Apps\6RAH\6RAH.APP`
  - Local (non-WSL) patched copy kept in sync: `C:\Users\Administrator\Downloads\Pocket Kingdom\System\Apps\6RAH`

## CRITICAL Data-File Facts (verified)
- The game **never opens `comp*.dat`** at runtime — no filename/byte reference of "comp" anywhere in `6RAH.APP`.
  Standalone `comp*.dat` files are dev/editor exports mirroring data already shipped inside `itemdata.dat`.
- The **live recipe tables are the 4704-byte TAIL of `itemdata.dat`** (and `english/itemdata.dat`):
  a byte-exact concatenation of the vanilla `comp*.dat` in sorted order
  (`comp00..comp86, comp90..comp96, compa0..compa6`) starting at file offset `0x4DF0`
  (`tail_base = filesize 24656 - 4704`). Known differences vs vanilla comp files: 5 ingredient-ID
  bytes in compa3/compa4 regions (`itemdata` 0x3a vs 0x36).
- Recipe table layout (16-byte entries start at +32; 32-byte header):
  - Tier tables (comp00-86, comp92-96, 48-80 bytes): header ff ff ff ff + 4 id bytes at +16..21;
    **success rate = byte/u16 at +22** (vanilla 80,75,70,65,60,55,50 / 70..50)
  - Emblem tables (comp90-91, compa0-6, 32-240 bytes): header ff ff ff ff ff ff at +16..21, rate byte at +22 = 0;
    **success rate = byte at entry+6** of each 16-byte entry (vanilla 90/80/80/70/60/50/40+)
  - Trophy/unique recipes (comp92-96 = category 07 bow tables, 48-80 bytes).
  - Per-recipe success rate = byte at +6 of every 16-byte entry in ALL table
    families (confirmed in-game: unique bow recipes showed vanilla 25/40/30/10/5%).
  - Table header byte at +22 = base/aggregate rate (also patched to 100).
- Save files: `save.dat`, `options.dat` under `C:\system\apps\6rah\` in the emulator (see `6RAH.cfg`).

## Local Modding & Patching Tools
- **Mass-sell:** `python3 tools/patch_mass_sell.py [path_to_6RAH.APP]`
  - Design: `MASS_SELL_DESIGN.md`; plan: `docs/superpowers/plans/2026-10-17-mass-sell.md`
  - Safety invariants: skip empty slots (0xFF), never sell equipped items (`0x100082E8` check),
    partial pages (<5 items) terminate cleanly, credited gold == exact price sum
- **100% combine rates:** `python3 tools/patch_100_percent_combine.py`
  - Patches rates in `comp*.dat` (dev copies) AND the live `itemdata.dat` + `english/itemdata.dat` tails
  - Emblem family detection must use the `ff ff ff ff ff ff` header marker — never the (mutated) rate byte
  - Creates `.orig` backups; idempotent (verified: second run = 0 byte changes)
- **Verification:** `python3 tools/verify_patch.py` (mass-sell hook + shellcode disassembly check)
- **Tests:** `PYTHONPATH=. python3 -m unittest discover tests` (8 tests, all green)
  - `tests/test_combine_rate.py` includes itemdata-tail rate assertions

## Workflow Rules
- Non-destructive patching: always create `.orig` backup before first modification; keep patchers idempotent.
- Never claim a mod works without concrete verification: run tests, byte-diff, or reproducible in-game check (EKA2L1).
- When adding shellcode: preserve `r4-r8, sb, sl, lr`; restore correctly to avoid corrupting game state.
- Distinguish pre-existing behavior from changes caused by edits: run tests BEFORE and AFTER.
- Report honestly: if broken and can't fix, say so; if skipped/assumed, state it.
