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
- RE analysis transcripts live in `docs/` (see `docs/comp_loader_points.md`).

### REA on THIS target (important)
- REA **cannot open `6RAH.APP` directly** — the Symbian E32Image is not a supported
  container (`target_unavailable / unsupported binary format`), and headerless
  `--target-format raw-binary` needs Ghidra (`GHIDRA_INSTALL_DIR`), which is not
  configured here. Only Hopper (`/opt/hopper`) is available as a native provider.
- Workaround: wrap the extracted text segment in an ELF32-ARM container, then REA
  analyses it with Hopper and all addresses match the game binary
  (`tools/wrap_raw_arm_elf.py 6rah_code.bin /tmp/6rah.elf` → 7 symbols →
  ~1060 procedures discovered):
  - `npx rea-agents analyze /tmp/6rah.elf --provider hopper`
  - `npx rea-agents xrefs /tmp/6rah.elf 0x1008fe2c --provider hopper`
  - `npx rea-agents decompile /tmp/6rah.elf --procedure merge_install --provider hopper`
  - `npx rea-agents instructions /tmp/6rah.elf --procedure 0x10028954 --provider hopper`
  - `npx rea-agents search /tmp/6rah.elf --kind strings --mode regex --pattern '.*' --provider hopper`
- Without symbols Hopper only discovers the entry point and `decompile` fails with
  "No procedure exists at the requested address" — pass function starts as symbols.
- Do **not** trust linear (capstone) sweeps of the whole text for caller checks: data
  islands desync the sweep and produced a wrong "0x1000cc40 has no callers" result.
  Decode per 4-byte word (ARM is fixed-width) or use REA `xrefs`/raw BL decoding.

## Symbian / N-Gage Binary Architecture
- **Main Executable:** `System/Apps/6RAH/6RAH.APP`
  - Format: Symbian E32Image (uncompressed EPOC binary, CPU: 0x2000 / ARMv4T)
  - Code Base: `0x10000000`, Code Offset: `0x7C`
  - Text Section Size: `0xB0CAC` (~724 KB); extracted code segment at repo root: `6rah_code.bin`
    (offset 0 of `6rah_code.bin` = VA `0x10000000`)
  - MultiBitmap Assets: `POKEKIN.MBM` (contains 488 bitmap sprites/UI elements)
  - Data Files: `System/Apps/6RAH/*.dat` and `System/Apps/6RAH/english/*.dat` (english dir = localized text; tails of `itemdata.dat` are identical)
- **Known subroutines (from RE, confirmed with REA/Hopper:**
  - `0x1000cc40` recipe-merge/install (`merge_install`); recipes resident at game-struct
    `M+0x480..0x4a4`, merge pointer `M+0x498` init at `0x10069900`.
    **5 direct BL callers**: `0x10028954`, `0x100289b4`, `0x10028c34`, `0x10028eac`,
    `0x10028f04` (all inside sub_10028538, the combine/merge screen driver).
    Signature: `merge_install(ctx, recipe_id, result_id, rate)` — 4th arg is the
    success rate, stored to `[merge_struct + 0x498]`.
  - `0x10035dac` combine-result text builder: reads the rate from
    `*(ctx+0x17914) + 0x18` and formats it with `"%d%%"` (`0x1008fe2c`; other copies
    at `0x100930a4`, `0x100aa070`). `*(ctx+0x17914)` == merge struct base (`M+0x480`),
    so `+0x18` == `M+0x498` — display and writer agree.
  - Combine screen state is slot-indexed with **52-byte stride**: recipe id at
    `ctx+0x73a0 + 52*slot`, rate at `ctx+0x73b8 + 52*slot`.
  - Resident recipe records at `ctx+0x19800+0x26c`, **196 bytes** each; the four
    ingredient ids sit at record `+0x78/+0x7c/+0x80/+0x84`
    (`0x2e4/0x2e8/0x2ec/0x2f0` with the 196-byte index math).
  - `0x10031428` item-info lookup.
- **Open question (not yet proven):** the exact loader step that turns the
  `itemdata.dat` tail byte at `entry+6` into the runtime rate at `ctx+0x73b8+52*slot`.
  The runtime value is a 32-bit slot field, so the file→runtime mapping still goes
  through one un-traced copy; everything else in the chain above is verified.
- **Testing Environment:** EKA2L1 Symbian Emulator on Windows host.
  - Windows share path: `\\wsl.localhost\archlinux\home\bossku\Pocket Kingdom\System\Apps\6RAH\6RAH.APP`
  - Local (non-WSL) patched copy kept in sync: `C:\Users\Administrator\Downloads\Pocket Kingdom\System\Apps\6RAH`
  - **RULE — ALWAYS COPY PATCHED FILES TO WINDOWS:** every time a game file changes
    (`6RAH.APP`, `itemdata.dat`, `english/itemdata.dat`, `comp*.dat`, …), immediately copy
    it to the Windows install above (WSL:
    `/mnt/c/Users/Administrator/Downloads/Pocket Kingdom/System/Apps/6RAH`) so EKA2L1 picks
    it up. Never copy `*.orig` backups there. Then verify with
    `diff -rq -x '*:Zone.Identifier' System/Apps/6RAH "/mnt/c/Users/Administrator/Downloads/Pocket Kingdom/System/Apps/6RAH"`
    (expect no `differ` lines). This copy step is part of "done" for any game-file change.

## CRITICAL Data-File Facts (verified)
- The game **never opens `comp*.dat`** at runtime — confirmed two ways: (a) no
  filename/byte reference of "comp" anywhere in `6RAH.APP`, and (b) REA string
  search over the analysed binary finds **zero** "comp" strings while
  `itemdata.dat` appears as 5 localized UTF-16 paths
  (`e:\System\Apps\6RAH\<lang>\itemdata.dat` for english/german/…, alongside
  `product.dat`, `item.dat`, `shop.dat`, `unit.dat`, …).
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
- **100% combine rates:** `python3 tools/patch_100_percent_combine.py [app_dir]`
  - Patches rates in `comp*.dat` (dev copies) AND the live `itemdata.dat` + `english/itemdata.dat` tails
  - Emblem family detection must use the `ff ff ff ff ff ff` header marker — never the (mutated) rate byte
  - Creates `.orig` backups for itemdata; idempotent (verified: second run = 0 byte changes)
- **E32Image → ELF wrapper (for REA):** `python3 tools/wrap_raw_arm_elf.py 6rah_code.bin /tmp/6rah.elf`
- **Tests:** `PYTHONPATH=. python3 -m unittest discover tests` (all green; self-skip without a game install)
  - `tests/test_combine_rate.py` includes itemdata-tail rate assertions

## Workflow Rules
- Non-destructive patching: always create `.orig` backup before first modification; keep patchers idempotent.
- Never claim a mod works without concrete verification: run tests, byte-diff, or reproducible in-game check (EKA2L1).
- **A patch being installed is not proof it behaves.** Byte-level "verification" only proves the
  bytes were written. The removed mass-sell patch passed every byte check yet never worked in game.
- Distinguish pre-existing behavior from changes caused by edits: run tests BEFORE and AFTER.
- Report honestly: if broken and can't fix, say so; if skipped/assumed, state it.

## Removed (do not re-apply without a real in-game test)
- **Mass-sell patch** (`tools/patch_mass_sell.py`, `verify_patch.py`, `assemble_hook.py`,
  `find_code_cave.py`, `MASS_SELL_DESIGN.md`, `docs/superpowers/`): it NOP'd a loop filter and
  loop bound at `0x100023EC`/`0x10002464` plus the quantity math at `0x100056A4`, but the path
  never credits gold (`0x10008BC4` unreachable from it) and did not sell a stack as intended.
  Confirmed broken in game. `6RAH.APP` is vanilla; code recoverable from git history.
