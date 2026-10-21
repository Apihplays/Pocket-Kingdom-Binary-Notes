---
id: effect-hp-absorption
status: verified
verified: 2026-10-21
addresses:
  - 0x1000eda8  # attack-time effect dispatcher
  - 0x1000f330  # HP Absorption 1 dispatch
  - 0x1000f350  # HP Absorption 2 dispatch
  - 0x10005e98  # drain, heal 1/3
  - 0x10005fdc  # drain, heal 2/3
tags: [effect, combat, drain, healing]
---

# Effects 27/28 — HP Absorption 1 / 2

> **TL;DR**
> - On a landing hit: damage the target for `ATK(wielder) − DEF(target)`, **min 3**.
> - Halve it while the target's effect-flag bit `0x1` is set.
> - The wielder heals **⅓** (effect 27) or **⅔** (effect 28) of the damage dealt.
> - Only applies to the wielder's equipped weapon/accessory proc, once per hit.

## Dispatch

`0x1000eda8(game, target, caster, id)` → table `0x1000ee68[id−1]`:

| id | idx | handler | routine |
|---|---|---|---|
| 27 | 26 | `0x1000f330` | `0x10005e98` (heal dmg/3) |
| 28 | 27 | `0x1000f350` | `0x10005fdc` (heal 2·dmg/3) |

Both handlers first test `[sp+0x10]` (0 = the accuracy roll succeeded) and bail on failure:

```
0x1000f330  ldr sb, [sp,#0x10]
0x1000f334  cmp sb, #0
0x1000f338  bne 0x1000f390
0x1000f33c  mov r0, r7          ; game
0x1000f340  mov r1, r8          ; caster / wielder
0x1000f344  mov r2, r5          ; target / victim
0x1000f348  bl  0x10005e98
```

## Drain maths (`0x10005e98`)

1. `r4 = ATK(r7)` via `0x10008490`, then element modifier `0x10009f94(game, r7, atk, 0)`.
2. `r5 → DEF(r5)` via `0x100084ec`, then `0x10009f94(game, r5, def, 0)`.
3. `r4 = atk − def`.
4. If `0x100082e8(game, victim) & 1` → `r4 >>= 1` (rounding-aware).
5. `if r4 <= 2: r4 = 3`.
6. `0x10008af4(game, victim, r4)` — subtract HP.
7. Heal: `0x10008bc4(game, wielder, r4/3)` (27) or `2*r4/3` (28, `lsl ip,r4,#1` at `0x10006064`).
8. Floating text at the victim's position, attributed to the wielder (`0x10005f38`+ / `0x1000607c`+).

## Caller chain

`0x1000e294` (hit branch) → `0x1000ec44` → per equipped slot →
`0x1000eda8` → `0x1000f330/0x1000f350` → `0x10005e98` / `0x10005fdc`.

The accuracy roll lives in `0x1000eda8` itself:
`rand()%100 < 4*min(5, HIT(wielder)) + DEX(wielder)/2` (`0x1000edd4`–`0x1000ee50`).

## Notes
- The drain is *extra* damage: it is separate from the weapon's normal hit.
- `0x10009f94` is the same element/affinity adjuster used by the main damage routine, so
  elemental weapons change the drained amount too.
- Effect 27/28 never trigger at battle start (the `0x1000f3a0` table no-ops ids 27–31).

## Open questions
- None at instruction level. In-game numbers still worth a spot check.
