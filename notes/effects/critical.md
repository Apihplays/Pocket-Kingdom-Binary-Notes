---
id: effect-critical
status: verified
verified: 2026-10-21
addresses:
  - 0x1000eda8  # attack-time effect dispatcher
  - 0x1000ee68  # jump table (index = id-1)
  - 0x1000f370  # Critical 1
  - 0x1000f378  # Critical 2
  - 0x1000f380  # Critical 3
  - 0x1000e6a8  # crit consumer in the damage routine
  - 0x1001f568  # innate Critical (unit 7/8)
  - 0x1001ac88  # innate Critical (third unit)
tags: [effect, combat, crit, damage]
---

# Effects 29/30/31 — Critical 1 / 2 / 3

> **TL;DR**
> - Chance on a landing hit: **10 % / 20 % / 30 %** (`rand()%100 <= 9 / 19 / 29`).
> - It sets unit bit `0x10000000`; the damage routine doubles damage and clears it.
> - **Quirk:** the handler sets the bit on the *victim* argument (`r5`), while the damage
>   routine reads it from the *attacker* (`r7`). Equipped Critical therefore does **not**
>   increase the wielder's own hit.
> - Innate Critical (units 7/8/9) uses a different path and does work.

## Dispatch

`0x1000eda8(game, target, caster, id)` is the attack-time effect dispatcher. Index = `id − 1`
into `0x1000ee68`; ids 29/30/31 land on `0x1000f370` / `0x1000f378` / `0x1000f380`.

```
0x1000f370  cmp  r2, #9        ; Critical 1
0x1000f374  b    0x1000f384
0x1000f378  cmp  r2, #0x13     ; Critical 2
0x1000f37c  b    0x1000f384
0x1000f380  cmp  r2, #0x1d     ; Critical 3
0x1000f384  ldrle r3, [r5,#0xc]
0x1000f388  orrle r3, r3, #0x10000000
0x1000f38c  strle r3, [r5,#0xc]
```

- `r2` is **the same** `rand()%100` used by the hit roll (computed `0x1000ee0c`–`0x1000ee24`).
- Unlike ids 1–28, this handler does **not** test `[sp+0x10]` (accuracy-success flag). In
  practice `0x1000ec44` is only reached after a successful hit, so it rarely matters.

## Who is `r5`?

`0x1000ec44(game, r6, r7)` (only caller `0x1000e294`, inside the hit branch) does:

1. `r4 = unit_lookup(r7)` — `0x10009a10` → `0x100707a4` resolves the live unit.
2. `0x1000ff6c(game, r6, r4)` — the attacker's innate ability.
3. Both equipped effect ids of **`r4`** are read from `ctx+0x4a8/0x5e0 + 52*slot` and passed to
   `0x1000eda8(game, r6, r4, id)`.

Inside the damage routine `r6` is the unit that **loses HP** (`0x10008af4(game, r6, dmg)` at
`0x1000e8bc`), so `r6` = victim and `r4` = attacker. Therefore in the dispatcher
**`r5` = victim, `r8` = wielder**.

The same dispatcher proves this independently: ids 27/28 call
`0x10005e98(game, r8, r5)`, which drains `r5` and heals `r8`.

## Consumer

```
0x1000e6a8  ldr r3, [r7,#0xc]      ; r7 = attacker (gets the 0x10000 attacker marker)
0x1000e6ac  tst r3, #0x10000000
0x1000e6b0  beq 0x1000e6d0
0x1000e6b4  lsl r4, r4, #1         ; x2 damage
0x1000e6b8  bic r3, r3, #0x10000000
0x1000e6bc  str r3, [r7,#0xc]      ; consumed
```

`0x1000e64c` marks `r7` with bit `0x10000` and `r6` with `0x40000`, so `r7` is the attacker.
Crit also swaps the hit sound: 8 instead of 11 (physical) / 12 (magic), `0x1000e6c0`–`0x1000e6f0`.

## Why equipment Critical is inert

The write goes to `[r5+0xc]` (victim); the read comes from `[r7+0xc]` (attacker). The bit is
cleared again at the start of the marked unit's next action:
`0x1001d18c`, `0x1001ec1c`, `0x100227ec`, `0x10022884` (`bic #0x10000000`).

## Innate Critical (works)

- `0x1001f568`: `[unit+0x6c] == 7` → threshold 10, `== 8` → 20; `cmp r4,r2; ldrgt` sets the bit
  on **`r5` = the acting unit** (`0x1001f594`).
- `0x1001ac88`: fixed threshold `0x1d` (30 %) on `r4` = the acting unit.
- Units: 7 Swordman, 8 Sword Master (10/20 %), 9 Mikaduchi (30 %).

## Open questions
- Exact reason the equipment path writes to the victim. Looks like a copy/paste from the
  stat-down handlers (ids 1–11 also act on the wrong register), but no alternate code path
  was found that consumes a victim-side crit flag.
