# Agent context — Pocket Kingdom binary notes

Read this file, then `notes/INDEX.md`, then **one** topic note. Don't re-read `CLAUDE.md`
unless you need project/tooling history.

## Target
- `System/Apps/6RAH/6RAH.APP` — E32 ARM image, code at file offset `0x7C`, VA base `0x10000000`.
- **Conversion:** `file_off = VA - 0x10000000 + 0x7C` (`va = 0x10000000 + file_off - 0x7C`).
- Text segment size `0xB0CAC`. Data files live next to it (`itemdata.dat`, `effect.dat`, …).

## Hard rules
- Never claim behaviour without an instruction address (or a reproducible in-game check).
- Mark each note `status: verified` or `status: inferred`; keep open questions visible.
- Do **not** linear-disassemble the whole text segment — capstone desyncs on data islands.
  Decode word-by-word or start from a known function/table address.
- `0x10000000` in `[unit+0xc]` = crit flag. A different `0x10000000` exists in the effect-flag
  word (survive-fatal-blow) — don't confuse them.

## Key addresses
| Thing | Address |
|---|---|
| Effect apply, battle start (id 0–43) | `0x1000f3a0`, table `0x1000f3d4` |
| Effect apply, attack time (id 1–31) | `0x1000eda8`, table `0x1000ee68` (index = id−1) |
| Equipment trigger per hit | `0x1000ec44(game, victim, wielder)` |
| Damage routine | `0x1000dfcc(game, defender)`, called from `0x10022230` |
| Stat getters (ATK/DEF/AGI/DEX/WIS/INT/HIT) | `0x10008490` / `0x100084ec` / `0x100085a4` / `0x10008714` / `0x100086b8` / `0x10008600` / `0x10008978` |
| Stat setters (ATK/DEF/AGI/DEX/WIS/INT) | `0x10009304` / `0x100093d0` / `0x10009700` / `0x10009634` / `0x10009568` / `0x1000949c` |
| Battle struct | `[ctx+0x1a590]` — gold `+0x960`, regen timers `+0x7a8`, hit timers `+0x7d8` |
| HP damage / heal | `0x10008af4` (subtract) / `0x10008bc4` (add, clamps) |
| Effect-flag word get / OR / clear | `0x100082e8` / `0x100081f0` / `0x1000826c` |
| Status ailments (apply) | `0x10007a3c` silence · `0x10007b28` poison · `0x10007c94` deadly · `0x10007e00` paralysis · `0x10007f48` sleep |
| Status bits (effect word) | silence `0x10` · poison `0x20` · deadly `0x40` · sleep `0x100` · paralysis `0x400` |
| Status immunity bits (`unit+0xc`) | poison `0x1000` · silence `0x2000` · sleep `0x4000` · paralysis `0x8000` |
| Natural cure (per action) | `0x1000a5f8` — `rand%100 < WIS/2` (sleep/poison), `< INT/2` (silence/paralysis) |
| `has_effect(ctx, unit, id)` | `0x1000a53c` |
| and `rng` | `0x100714e8` (`rand()`), `%100` done inline |

## Records
- **Stat record**: 92-byte stride, player base `ctx+0x00`, enemy base `ctx+0x228`.
  `+0x00` id, `+0x04` HIT, `+0x14` ATK, `+0x18` DEF, `+0x1c` curHP, `+0x20` maxHP,
  `+0x24` AGI, `+0x28` DEX, `+0x2c` WIS, `+0x30` INT.
- **Unit struct**: `+0xc` state bits, `+0x6c` unit id, `+0x70` anim state, `+0x74` side,
  `+0x78` slot, `+0x80` x, `+0x84` y.
- **Equipped records**: `ctx+0x4a8 + 52*slot` (player), `ctx+0x5e0 + 52*slot` (enemy),
  item id at `+0x00` (`0xff` = empty), effect ids at `+0x0c` and `+0x10`.
- **Effect IDs are 0-based** indices into the 52-name table (`effect.dat`, UTF-16BE records;
  `english/itemdata.dat` @ `0x00F0`, 52×48 UTF-16LE). 0–11 = stat Up/Down, 12/13 = Sleep/D.Sleep,
  14 = Sleep Res, 15/16 = Paralysis, 17 = Paralysis Res, 18/19 = Poison/Deadly, 20 = Poison Res,
  21/22 = Silence/Strong, 23 = Silence Res, 24–26 = Auto HP Restore, 27/28 = HP Absorption 1/2,
  29–31 = Critical 1/2/3, 32–34 = Counter, 35–37 = Phys Red, 38/39 = Magic Red/Reflection,
  44–48 = Self Destruct / Regenerate / Multiply / Revive / Item Recovery, 49–51 = Gold Recovery Up.

## Data facts that bite
- `comp*.dat` is **never opened** by the game; live recipe data is the 4704-byte tail of
  `itemdata.dat` + `english/itemdata.dat`.
- `itemdata.dat` in the default folder is Spanish; English strings are in `english/itemdata.dat`.
- Two separate 0x10000000 bits (see Hard rules).
