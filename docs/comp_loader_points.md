# comp*.dat loader investigation — Pocket Kingdom (6RAH.APP)

Binary: `System/Apps/6RAH/6RAH.APP` (E32Image, code base `0x10000000`).
All VAs below are code-base VAs; file offsets in descriptors are raw APP offsets.

## 1. Is there a comp*.dat loader? — NO. Verdict: not loaded by this binary.

Evidence, five independent checks:

1. **Complete filename-literal inventory.** All UTF-16 descriptors in the whole APP
   (4-byte length + string, scanned every 4-byte offset, deduped) = 175 strings,
   of which 70 are filenames. The complete filename list (`/tmp/opencode/allstr2_names.txt`):
   `partydata, battlemes×5, itemdata×5, product, dropitem, itemshop, clearitem,
   area×5, move×5, mapinfo, mestext×5, opening×5, ending×5, pausemess×5,
   secretary, sec_name, demo, staff, questmes×5, questitem, save, options,
   `\_\_101fd3dd\_\_.ini`, unit×5, unitshop, name, action, rankup, partyaction,
   unitcol`, plus `e:\game.id`, `pokeport.mbm`, `6rah.cfg`, `6rah.mbm`,
   `grow.pcm`, `whiskaway1.pcm`, `neon_light.pcm`. **No `comp` of any kind.**
2. **Byte-level absence.** ASCII `comp` (0 hits), ASCII pairs `co`/`mp` (0 hits in
   code.bin), UTF-16 `comp` (0 hits in the entire APP file), BE-packed word
   `0x636F6D70` / `0x706D6F63` (0 hits). Also 0 for `atrb`, `e ff`, `equip` — same
   unreferenced family.
3. **Runtime char construction impossible.** Sweep over every `mov/orr/add/sub/mvn/
   bic/eor/rsb` immediate for byte value `0x6D` ('m'), including ARM 8-bit-rotated
   encodings and MVN complements (rotations of imm8): `'c'` = 5 hits (all are the
   loop constant 99), `'o'` = 1 hit (`0x10031c54`, UI element id), `'m'` = 0 hits,
   `'p'` = 90 hits (all `sp/#0x70` stack frames). No `strb`-to-descriptor building
   loop exists (all `ldrb`/`strb` operands hit game-object fields, not ring buffers).
4. **No wildcard enumeration.** No directory-scan patterns (`*.dat`, `comp*`,
   `?`) as Symbian descriptors anywhere.
5. **The dynamic-name precedent exists and uses literal stems.** The Fabbis
   subsystem builds filenames at runtime as
   `e:\System\Apps\6RAH\Fabbis\<lang>\` (dir literal ×10: `0x100a0f12`..)
   + stem literals `Ingr` at `0x100a109c` and `info` at `0x100a108c`
   + number/suffix formats `%03d.txt` `0x100a0a5c`, `%03db.txt` `0x100a0a78`,
   `%03da.txt` `0x100a0a8c`. This matches the on-disk `Fabbis/<lang>/Ingr000a.txt`
   etc. A comp loader would need the same machinery — the `comp` stem simply
   does not exist in the binary.

Consequence: `comp*.dat` (77 files), `item0–item4.dat`, `equip0–2.dat`,
`atrb.dat`, `effect.dat`, `quest_weapon/armor/accessories.dat` form one coherent
set of **never-referenced files** — dev/derived data, not read at runtime by the
shipped code. Only one mapinfo-like hit exists in text files ("completely" in
mapinfo.dat), which is prose, not a filename.

## 2. What the comp*.dat files actually contain (format established from data)

Vanilla values below come from the `.orig` backups (68 files, see
`/tmp/opencode/orig_cmp.txt`), i.e. pre-patch originals.

* Header (48-byte files): `u16 count` at +0, `u32 ff ff ff ff`, `u16 head-id` at
  +0x14, **`u16 head-rate` at +0x16 (byte 22 = low byte)** — vanilla values
  80/75/70/65/60/55/50 per page. (`comp90`, `comp91` are 32-byte header-only.)
* Entries: stride 16 from file offset 32: `3 × u16 ingredient ids` then
  **`u16 rate at entry+6 (bytes 6–7, LE)`** — vanilla 30/25/20/15/10/5.
  So the rate is a **u16**, not a byte; patching only byte +6 while leaving
  byte +7 = 0 is correct as-is.
* Emblem tables `compa0–compa6` (and high-tier `comp92–96`): same entry layout;
  vanilla emblem entry rates are already all `0x64` = **100** (no `.orig` was
  created for compa* by the rate patcher, consistent with "nothing changed"),
  e.g. `compa0.dat` = 14 entries, every `u16[+6] = 0x0064`.
* The ingredient-id vocabulary is shared with `product.dat`: identical u16 IDs
  (e.g. `0x3403`, `0x0902`, `0x1703`). `compNN.dat` per file = one result item's
  recipe table; `product.dat` (referenced!) holds the same 86 distinct u16 IDs.
  → comp*.dat is the dev-side rendering of the live combine data, whose shipped
  source is the referenced `product.dat` / `itemdata.dat` family.

## 3. The %d%% display paths (verified code)

Three "%d%%" format descriptors exist: `0x1008d3d8`, `0x1008fe2c`, `0x100930a4`.

* **Item-info screen** `0x10031428`: at `0x10031564..0x1003157c`
  `ldr r1,[pc,#0x100]` (→ pool `0x10031670` = `@0x1008d3d8 "%d%%"`), then
  `bl 0x1007bd64` (descriptor ctor) and `bl 0x1007bd74` (Format AppendNum) with
  `r2 = [r6+0x498]` where `r6 = *(gamestruct + 0x1AAA8)` — the combine/inventory
  manager instance `M`.
* `M+0x498` has exactly **one writer**: `0x1000d3e0`
  (`str ip,[r3,#0x498]`, `r3 = *(r6 + literal 0x1AAA8)`) inside recipe-install
  function `0x1000cc40`, value = arg `r3` of that function.
* `0x1000cc40` fills the per-recipe summary block `M+0x480..0x4a4`
  (`0x480 id`, `0x484 sub`, `0x488/0x48c u8 inputs`, `0x490/0x494 rate sums`,
  `0x498`, `0x49c`, `0x4a0`, `0x4a4`) from the game struct's tables at
  `+0x196c0..` / `+0x2740..` / `+0x19800..` and copies 0x228-byte records
  (`0x1000d028..0x1000d0f4` bulk u32 copy of 0x58 bytes) from resident tables.
* Callers of `0x1000cc40` (5 sites, all in `0x10028900–0x10028f04`, e.g.
  `0x10028954` passes `r3 = [big+0x7300+0xb8+k*64]`; `0x10028c34` passes `r3 = 0`
  and `r2 = 0xd`; `0x10028eac` passes `r3 = 0xd`) — i.e. the value at `M+0x498`
  comes from **resident in-memory tables**, not from any file read in this path.
* Other `%d%%` consumers: status screen `0x10035dac` formats
  `[ *(save+0x17914) + 0x18 ]` (pool `0x10036064` = `0x17914`), and screen
  `0x1003d280` uses pool `0x1003d508` = `0x18618`. These are per-screen status
  values (e.g. capture/probability readouts), separate from combine.

## 4. Verdict on the patch questions

* **Is `hdr byte22` or `entry+6` the success-rate byte the game uses?**
  Neither is used by the shipped binary — no code reads comp*.dat at all
  (Section 1). Inside the file format itself both fields exist as **u16**:
  header rate `u16 @ +0x16` and per-entry rate `u16 @ entry+6`; vanilla values
  per above table. So `tools/patch_100_percent_combine.py` edits real fields of
  real files — but files the game never opens.
* **Would patching `compa*` set emblem combines to 100%?** No effect in the
  emulator. And the emblem entry rates in `compa0–6` are already 0x64=100
  in these files, so even a working loader would not change in-game behavior.
* **Where the real (displayed) rates come from:** the in-memory tables
  installed by `0x1000cc40` (Section 3), sourced from referenced data files
  (`product.dat` / `itemdata.dat` family — same u16 ID vocabulary).
  `itemdata.dat` already contains a trailing `u16 0x64` (=100) field in the
  12 weapon-class records (`…ff ff 01 00 00 00 00 64`), same field layout as
  the unreferenced dev file `item0.dat` (every record `…ff ff 01 00 00 00 64`).

## 5. Recommended next steps (definitive)

1. Run the game under EKA2L1 (already configured per `CLAUDE.md`) and log
   `RFile::Open` requests — will show exactly which data files the live
   combine code opens (expected: product.dat / itemdata.dat, and empirically
   **not** comp*.dat). This closes the loop statically established here.
2. Decode `product.dat` (1024 bytes, u16 streams split by `00 00` separators,
   86 distinct IDs — matches comp00…comp86 count) and `itemdata.dat`
   (24,656 bytes, 48-byte stride records with `u16 0x1b` tag + trailing rate
   u16) to locate the live rate field.
