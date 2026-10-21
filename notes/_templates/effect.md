---
id: effect-template
status: inferred
verified: YYYY-MM-DD
addresses: []
tags: [effect]
---

# Effect NN — Name

> **TL;DR**
> - What it does, in game terms (damage/chance/duration).
> - Where it is dispatched from, and which register holds the affected unit.
> - Any quirk a player or modder would notice.

## Dispatch
`table[id] -> handler` — list the table address, index formula, and gate conditions
(accuracy roll, status bits, effect-flag bits).

## Flow
1. Step with address and the register that carries each value.
2. …
3. Final write (`0x10008af4` damage, `0x10008bc4` heal, `0x100081f0` flag OR, …).

## Quirks
- …

## Evidence
- Raw instruction(s) and their encoding, if the decode is surprising.
- Caller chain: `0x… -> 0x… -> 0x…`.

## Open questions
- …
