# Technical Design: Mass-Sell Feature for Pocket Kingdom (N-Gage / EKA2L1)

**Target:** Nokia N-Gage Symbian OS 6.1 / 7.0s (`6RAH.APP`)  
**Architecture:** ARMv4T (32-bit ARM mode)  
**Status:** Draft Specification  

---

## 1. Background & Problem Statement
In *Pocket Kingdom: Own the World*, selling items in the shop requires selecting an item individually, choosing the sell action, confirming the sale dialog, and waiting for the inventory to update. With inventory counts frequently reaching hundreds of equipment pieces and drops, cleaning inventory item-by-item is a primary point of player friction.

The goal is to implement a mass-sell mechanism that allows selling all eligible items on the current page (up to 5 items) in a single transaction.

---

## 2. Reverse-Engineered Architecture

### 2.1 Binary Layout
- **Executable:** `System/Apps/6RAH/6RAH.APP`
- **Format:** Symbian E32Image (uncompressed EPOC binary)
- **Base Address:** `0x10000000`
- **Code Segment File Offset:** `0x7C`
- **Text Section Size:** `0xB0CAC` bytes (~724 KB)

### 2.2 Core Shop Subroutines Identified

| Address | Subroutine Purpose | Arguments / Registers |
|---|---|---|
| `0x10006690 - 0x1000680C` | Shop Sell Page Loop (5 items per page) | `r7 = game_ctx`, `r8 = shop_ctx`, `r6 = loop_counter (0..4)` |
| `0x100084EC` | Fetch Item Gold Price | `r0 = game_ctx`, `r1 = item_ref` $\rightarrow$ `r0 = price` |
| `0x100082E8` | Check Item Status (equipped, locked, quest item) | `r0 = game_ctx`, `r1 = item_ref` $\rightarrow$ `r0 = status_mask` |
| `0x10008AF4` | Deduct Item from Inventory | `r0 = game_ctx`, `r1 = item_ref`, `r2 = count_delta` |
| `0x10008BC4` | Add / Credit Item or Gold | `r0 = game_ctx`, `r1 = item_ref / currency`, `r2 = amount` |

### 2.3 Shop Sell Page Loop Structure
In `0x10006690`:
- `r6` serves as the visible row index on the active screen:
  ```arm
  0x100067f0:  add    r6, r6, #1
  0x100067f4:  cmp    r6, #5
  0x100067f8:  b      #0x10006800
  0x10006800:  ble    #0x100066a4   ; Loop back for next item on page
  ```
- Before displaying each item, `0x100082E8` checks if the item can be sold (`tst r0, #1`).

---

## 3. Mass-Sell Design Options

### Option A: "Sell All On Page" Action Hook (Recommended)
- **Concept:** When confirming the sell action on the current menu, the execution loop does not terminate after one item. Instead, it iterates through indices `0..4` of the currently visible page slot buffer.
- **Safety Checks:**
  1. Skip slots where item pointer is null or empty (`0xFF`).
  2. Skip equipped items (`0x100082E8` check).
  3. Deduct each valid item via `0x10008AF4`.
  4. Accumulate total gold and credit the player in a single transaction call.
- **Trigger:** Either mapped to an existing multi-use key (e.g., Softkey 2 / '*' key / Edit key) or replaces the single-sell routine when holding a modifier key.

### Option B: Page-Level Multi-Selection (Checkbox)
- **Concept:** Add a 1-byte selection bitmask (bits 0..4) in unused scratchpad memory in the shop context.
- **UI:** Render a check indicator beside checked rows using an existing icon glyph from `POKEKIN.MBM`.
- **Action:** Selling processes only the checked bits in the bitmask.

---

## 4. Implementation Steps & Validation
1. **Locate Code Cave / Trampoline:**
   - Locate unused padding or function alignment space in `6RAH.APP` for the injected multi-sell loop routine.
2. **Implement Hook Handler (ARM Assembly):**
   - Save registers (`push {r4-r8, lr}`).
   - Loop `r6` from `0` to `4`.
   - Resolve item address for current page slot.
   - Verify unequipped status.
   - Call `0x10008AF4` (deduct item) and `0x10008BC4` (add gold).
   - Restore registers and trigger UI refresh (`0x10069D58`).
3. **Deploy & Test via EKA2L1:**
   - Test in EKA2L1 emulator with save state before shop entry.
   - Verify:
     - All 5 visible items are removed from inventory.
     - Total gold increases by the exact sum of individual sale prices.
     - Equipped items remain untouched.
     - No memory leaks or invalid pointer dereferences on partial pages (< 5 items).
