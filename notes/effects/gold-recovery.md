---
id: effect-gold-recovery
status: verified
verified: 2026-10-21
addresses:
  - 0x1000d900  # battle-result routine
  - 0x1000d9a4  # party effect-slot scan (ids 0x31/0x32/0x33)
  - 0x1000dac4  # tier jump table (0x1000dacc)
  - 0x1000dae0  # tier 1: x1.2
  - 0x1000db14  # tier 2: x1.5
  - 0x1000db34  # tier 3: x2.0
  - 0x1000aecc  # reward -> money counter
  - 0x100710d0  # ctx+0x438 += amount (clamped)
tags: [effect, economy, battle, gold]
---

# Effects 49/50/51 — Gold Recovery Up 1 / 2 / 3

> **TL;DR**
> - Multiplies the battle's gold reward by **×1.2 / ×1.5 / ×2.0** (integer truncation).
> - Rolled once at battle end in `0x1000d900`, which scans all four party slots' two equipment
>   effect slots. The **highest** tier found wins; duplicates never stack.
> - The reward lives at `battle+0x960` (`battle = [ctx+0x1a590]`) and is later added to the money
>   counter `ctx+0x438` through `0x100710d0`.
> - Name mismatch: `effect.dat` says **Gold** Recovery Up, `english/itemdata.dat` says **loot**
>   Recovery Up. The code (and the ×1.2/1.5/2.0 progression on a gold counter) proves gold.

## Scan

```
0x1000d99c  mov  r5, #0                ; slot = 0
0x1000d9a0  mov  r4, r5                ; tier = 0
0x1000d9a4  ...  r1 = ctx + 0x4b4      ; equipment +0x0c (effect slot 1)
0x1000d9bc  ldr  r3, [r1, 52*slot]
0x1000d9c0  cmp  r3, #0x31             ; Gold Recovery Up 1
0x1000d9ec  cmp  r4, #0
0x1000d9f0  moveq r4, #1
0x1000da08  ...  r2 = ctx + 0x4b8      ; equipment +0x10 (effect slot 2)
0x1000da24  cmp  r3, #0x32             ; tier 2
0x1000da50  cmp  r4, #0
0x1000da54  movle r4, #2
0x1000da7c  cmp  r3, #0x33             ; tier 3
0x1000da84  mov  r4, #3                ; unconditional
0x1000dab4  add  r5, r5, #1
0x1000dab8  cmp  r5, #3
0x1000dabc  ble  #0x1000d9b4
```

- `52*slot` comes from `add r3,r5,r5,lsl#1` + `add r3,r5,r3,lsl#2` → `13*slot`, then `lsl#2`.
- Slot stride `52` is the equipped-record size (`ctx+0x4a8`, see
  [battle records](../systems/battle-records.md)); `+0xc` / `+0x10` are the two effect ids.
- The scan does **not** check whether the unit is alive or on the field — a fallen or benched
  member's accessory still counts, as long as its equipment record holds the id.
- Tier 1 only sets `r4=1` when `r4==0`; tier 2 only when `r4<=0`; tier 3 always. So 3 > 2 > 1,
  and two copies of the same tier are idempotent.

## Multipliers

`0x1000dac0` `cmp r4,#3` / `0x1000dac4` `ldrls pc,[pc,r4,lsl#2]` uses PC+8 = `0x1000dacc`;
the table stores absolute handler addresses (not branch words):

| tier | handler | code | result |
|---|---|---|---|
| 0 | `0x1000db48` | — | unchanged |
| 1 | `0x1000dae0` | `6x * 0x66666667 >> 32 >> 1` | `1.2x` |
| 2 | `0x1000db14` | `(3x + (x>>31)) >> 1` | `1.5x` |
| 3 | `0x1000db34` | `x << 1` | `2.0x` |

Tier 1 in full:

```
0x1000dae0  ldr  r3, [pc, #0x24]     ; 0x1a590
0x1000dae4  ldr  r1, [r6, r3]        ; battle
0x1000dae8  ldr  r3, [r1, #0x960]    ; base reward
0x1000daec  add  r3, r3, r3, lsl #1  ; 3x
0x1000daf0  lsl  r3, r3, #1          ; 6x
0x1000daf4  ldr  r2, [pc, #0x14]     ; 0x66666667
0x1000daf8  smull sb, r2, r3, r2
0x1000dafc  asr  r3, r3, #0x1f       ; sign
0x1000db00  rsb  r3, r3, r2, asr #1  ; (high>>1) - sign
0x1000db04  str  r3, [r1, #0x960]
```

`0x66666667 / 2^32 ≈ 0.4`, so `6x·0.4 = 2.4x`, then `>>1` → `1.2x`. Tier 2 computes `3x/2`
with sign correction (truncate toward zero); tier 3 is a plain `<<1`.

## Where the reward goes

The base reward is built just above (`0x1000d964`–`0x1000d994`):
`100*items + 200*elite_count`, `+1000` when every enemy qualifies, stored to `battle+0x960`.
The tier multiplier runs afterwards, so the flat bonus is multiplied too.

Later `0x1000aec0` re-reads `battle+0x960` and calls `0x100710d0(ctx, value)`:

```
0x100710d0  ldr  r3, [r0, #0x438]
0x100710d4  add  r1, r1, r3
0x100710d8  str  r1, [r0, #0x438]    ; clamp to [0, max]
```

`ctx+0x438` is money: the shop purchase check at `0x10046b24`–`0x10046b30` compares
`[ctx+0x438]` against the price table and refuses the buy when `gold <= price`.

## Evidence

- Tier words at `0x1000dacc..0x1000dad8` are absolute addresses (`0x1000db48`, `0x1000dae0`,
  `0x1000db14`, `0x1000db34`) — `ldr pc,[pc,r4,lsl#2]` jumps to the loaded word directly.
- Literal `0x1000db10 = 0x66666667`, `0x1000db30`/`0x1000db68 = 0x1a590`.
- Name tables: `effect.dat` record 49 = "Gold Recovery Up 1"; `english/itemdata.dat` @
  `0xF0 + 49*48` = "loot Recovery Up 1".

## Open questions

- Does the reward screen show the multiplied value, or the base? The `%d` draw at
  `0x1000bab8` / `0x1000bf4c` reads `battle+0x960` *after* this routine, so it should show the
  multiplied value — not confirmed in-game.
- `ctx+0x434` (adjusted by `battle+0x95c`, `-min([0x434],30)`) is a second, unrelated counter.
  Its meaning (VP?) is still open.
