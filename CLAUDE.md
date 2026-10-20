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
  - Game install: `<game-install>\System\Apps\6RAH` (machine-specific; not published)

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

## Item effects 40-48 (verified 2026-10-20)
Effect **names** are data (`effect.dat`; `english/itemdata.dat` @ `0x00F0`, 52 x 48-byte
records), but the **mechanics are hard-coded**. Dispatcher for effects 0..43:

- `0x1000f3a0` = effect-apply routine; `0x1000f3c8` is
  `cmp r2,#0x2b; ldrls pc,[pc,r2,lsl#2]` with the 44-entry table at `0x1000f3d4`.
  Cases: 40 `0x1000facc`, 41 `0x1000fb34`, 42 `0x1000fc04`, 43 `0x1000fcd4`.
- Handlers multiply the unit's **battle stat** fields in place:
  - 40 Proof of Contract: `INT +50%` (`stat + stat/2`, floor)
  - 41 Warrior's Spirit: `ATK +30%`, `DEF +30%`
  - 42 Mage's Spirit: `INT +30%`, `WIS +30%`
  - 43 Hero's Spirit: ATK/DEF/AGI/DEX/WIS/INT `+30%` each
- +30% is `stat + (((0x66666667 * 3*stat) >> 32) >> 2)` == `floor(1.3*stat)`.
- Stat map (proved by the getters/setters the ATK/DEF/AGI/DEX/INT/WIS Up cases use):
  `ATK +0x14`, `DEF +0x18`, `AGI +0x24`, `DEX +0x28`, `WIS +0x2c`, `INT +0x30`;
  the enemy copy is `+0x228` higher (`ctx+0x23c..0x258`).
- Applied per equipped effect slot: caller `0x10020f3c` reads slot fields `+0xc` and `+0x10`
  (records at `ctx+0x4a8 + 52*slot` for the player, `ctx+0x5e0 + 52*slot` for the enemy) and
  calls the dispatcher twice — duplicates stack (two Hero's Spirit = x1.69).
- Items: 40 = Emperor's Staff, Mage Necklace; 41 = Wolf Ring; 42 = Owl Ring;
  43 = Ring of the Sun; 44 = Hellfire Axe; 45 = Rebirth Necklace; 46 = Dividing Necklace;
  47 = Armored Casket; 48 = Soul Jacket.
- HP fields: current `+0x1c`, max `+0x20` (enemy `+0x244` / `+0x248`); heal helper
  `0x10008bc4` adds then clamps to max. `has_effect` helper = `0x1000a53c(ctx, unit, id)`.

Effects 44-48 are **not** in the 0..43 dispatcher — they are procs checked elsewhere:

- 44 Self Destruct (death): `0x1000dfcc` (caller `0x1002226c`), `has_effect(...,0x2c)` at
  `0x1000e2ec`; blast routine `0x10007700` hits enemies within 59 px (`cmp r2,#0x3b`),
  damage = user's current HP - target DEF (`0x100084ec`, min 1), halved while defending.
- 45 Regenerate: turn start sets bit 31 of the slot status word
  (`0x1001e9dc` -> `0x100081f0(...,0x80000000)`); after the move animation `0x1001edc0`
  rolls `rand%100 <= 9` and heals `maxHP/2` (`0x10008cf4` -> `0x10008bc4`).
- 46 Multiply: `0x1001d318` `has_effect(...,0x2e)` then `rand%100 <= 9` -> `0x1001d5a8`
  copies the 92-byte battle record (stats + current HP) into a free slot; `0x1000a394`
  only tests slots 4-5 and returns `0xff` when full.
- 47 Revive: death handler `0x10008ec4` compares the slot to `0x2f`, consumes it (`0xff` at
  `0x10008f50`) and restores `maxHP/2`.
- 48 Item Recovery: post-battle cleanup (`0x1007b0f8`, called from `0x1000b5b0` when the
  battle state is 5) sets a flag at `0x1007b1ec`/`0x1007b228`; `0x1007b3b8` applies a
  `rand & 1` roll in the item-removal pass (inventory semantics not fully decoded).
- 49-51 loot recovery is separate, in the drop routine at `0x1000d900`.
- Auto HP Restore 24-26 is **not** the same: it arms a 33-tick timer at `ctx+0x7a8+slot*28`
  and heals a small flat amount (2/5/10) when it expires. Regenerate is the 50%-max-HP proc.
- The 40-43 buff lands on the battle array, so the menu stat screen does not show it.
- Compendium source of truth: `EFFECT_BEHAVIOR` in `tools/build_unitdb.py` →
  `unitdb/effects.json` / `.csv`; rerun the full build to refresh the app.

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
