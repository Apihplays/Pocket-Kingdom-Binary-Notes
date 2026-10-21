---
id: system-effect-dispatch
status: verified
verified: 2026-10-21
addresses:
  - 0x1000f3a0  # battle-start / passive dispatcher
  - 0x1000f3d4  # its 44-entry jump table (index = id)
  - 0x1000eda8  # attack-time dispatcher
  - 0x1000ee68  # its 31-entry jump table (index = id-1)
  - 0x1000ec44  # per-hit equipment trigger
  - 0x10020f3c  # battle-start equipment trigger
tags: [system, dispatch, effects]
---

# Effect dispatch — the two jump tables

> **TL;DR**
> - Two switch tables, two different index conventions.
> - `0x1000f3a0(game, unit, id)` uses `table[id]`, ids **0–43**, passive/battle-start only.
> - `0x1000eda8(game, target, caster, id)` uses `table[id−1]`, ids **1–31**, rolls accuracy.
> - Inside `0x1000eda8`: **`r5` = target, `r8` = caster**. Proven by HP Absorption (27/28).
> - Effect ids are **0-based** record indices into the 52-name table.

## Passive dispatcher — `0x1000f3a0`

```
0x1000f3b0  cmp r2, #0xff          ; 0xff = empty slot
0x1000f3b4  beq 0x1000ff60
0x1000f3c8  cmp r2, #0x2b          ; 0..43
0x1000f3cc  ldrls pc, [pc, r2, lsl #2]
0x1000f3d0  b 0x1000ff60
```

- Table base `0x1000f3d4` (`ldrls pc` sees `PC = 0x1000f3cc + 8`).
- Index is the **raw id**. Ids 44–48 are out of range here (they are attack-time procs).
- Ids 27–31 are wired to the default case (`0x1000ff60`) — nothing to arm at battle start.

## Attack dispatcher — `0x1000eda8`

```
0x1000edc8  cmp r3, #0xff          ; empty slot -> return success
0x1000ee54  ldr sb, [sp,#0x14]     ; id
0x1000ee58  sub r3, sb, #1
0x1000ee5c  cmp r3, #0x1e          ; 1..31
0x1000ee60  ldrls pc, [pc, r3, lsl #2]
```

- Table base `0x1000ee68` (`PC = 0x1000ee60 + 8`), 31 entries.
- Result of the accuracy roll is kept in `[sp+0x10]`: **0 = hit, 1 = miss**. Handlers for
  ids 1–28 bail on 1; ids 29–31 (Critical) do not test it.

### Accuracy roll (inside the same function)

```
r4 = 4 * min(5, HIT(caster))        ; 0x10008978
r4 += DEX(caster) / 2               ; 0x10008714
r2 = rand() % 100                   ; 0x100714e8
success = (r2 < r4)
```

`caster` is `r8`, i.e. the second argument. Failure sets `[sp+0x10] = 1`; the function returns
that value in `r0`.

## Argument convention

`0x1000eda8` is called with `(game, target, caster, id)`:

- Equipment proc: `0x1000ec44(game, victim, attacker)` resolves the attacker, then calls
  `0x1000eda8(game, victim, attacker, effect_id)` for each of the two equipped effect slots.
- Proof: ids 27/28 call `0x10005e98(game, r8, r5)`, which uses `ATK(r8) − DEF(r5)`, subtracts HP
  from `r5` and heals `r8`. The victim must be `r5`, the drainer `r8`.

Consequence: any handler that writes a **self-buff** by mistake writes it to the victim.
Critical 29–31 does exactly that (see [critical.md](../effects/critical.md)).

## Which caller triggers what

| Caller | Context | Slots |
|---|---|---|
| `0x10020f3c` | battle start, per unit | both equipped slots (`+0xc`, `+0x10`) → `0x1000f3a0` |
| `0x1000ec44` | every landing hit | same two slots → `0x1000eda8` |
| `0x1000733c` | ability effect apply | one explicit id |
| `0x10010168` | weapon-skill states | one explicit id |
| `0x1001bb24` | enemy ability state machine | id 1 (ATK Down) |

## Id numbering

The 52 names are 0-based records: `0 = ATK Up` … `27/28 = HP Absorption 1/2`,
`29–31 = Critical 1/2/3`, `32–34 = Counter`, `35–37 = Phys Red`, `38/39 = Magic Red/Reflection`,
`44–48 = Self Destruct / Regenerate / Multiply / Revive / Item Recovery`.

This is confirmed by the passive table: index `32` arms the Counter 1 bit, index `35` the
Phys Red 1 bit, index `40–43` the spirit/contract buffs — exactly the 0-based records.

## Open questions
- `0x1000dfcc` only processes roster entries whose `[+0x6c] == 0xc0`. That value is not a unit id
  from the database; it looks like an attack-state marker. Not yet explained (see
  [battle-records.md](battle-records.md)).
