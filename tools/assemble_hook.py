import struct

def arm_branch(from_addr: int, to_addr: int, link: bool = False) -> int:
    """Computes a 32-bit ARM B or BL instruction opcode."""
    offset = (to_addr - (from_addr + 8)) >> 2
    offset &= 0x00FFFFFF
    cond = 0xEB000000 if link else 0xEA000000
    return cond | offset

def generate_mass_sell_shellcode(cave_addr: int, return_addr: int) -> bytes:
    """
    Generates ARMv4T shellcode for Pocket Kingdom to iterate over the 5 items
    on the current page, check each item's validity, and sell them all in sequence.
    """
    insns = []
    cur_addr = cave_addr

    def emit(word: int):
        nonlocal cur_addr
        insns.append(struct.pack("<I", word))
        cur_addr += 4

    # 1. Save registers: push {r4, r5, r6, r7, r8, sb, sl, lr}
    emit(0xE92D4DF0)

    # 2. r7 holds game context, r8 holds shop context. Init loop counter r6 = 0
    # mov r6, #0
    emit(0xE3A06000)

    loop_start_addr = cur_addr

    # 3. Locate item pointer for index r6
    # In 6RAH.APP:
    # ldr r3, [pc, #constant] -> r1 = [r7, r3]
    # For simplicity, resolve item pointer via the shop page table:
    # Check if r6 < 5, else exit loop
    # cmp r6, #5
    emit(0xE3560005)

    # bge loop_exit (forward branch, will compute target)
    exit_branch_idx = len(insns)
    emit(0) # placeholder

    # Check item status:
    # mov r0, r7 (game_ctx)
    emit(0xE1A00007)
    # mov r1, r6 (slot index)
    emit(0xE1A01006)

    # Call 0x100082e8 to check equipped/valid status
    # bl 0x100082E8
    emit(arm_branch(cur_addr, 0x100082E8, link=True))

    # tst r0, #1 (if equipped or invalid, skip)
    emit(0xE3100001)

    # bne next_item
    skip_branch_idx = len(insns)
    emit(0) # placeholder

    # Deduct item:
    # mov r0, r7 (game_ctx)
    emit(0xE1A00007)
    # mov r1, r6 (item / slot index)
    emit(0xE1A01006)
    # mov r2, #1 (quantity 1)
    emit(0xE3A02001)
    # bl 0x10008AF4 (deduct transaction)
    emit(arm_branch(cur_addr, 0x10008AF4, link=True))

    next_item_addr = cur_addr
    # Fix skip branch
    insns[skip_branch_idx] = struct.pack("<I", arm_branch(cave_addr + skip_branch_idx * 4, next_item_addr, link=False))

    # add r6, r6, #1
    emit(0xE2866001)

    # b loop_start
    emit(arm_branch(cur_addr, loop_start_addr, link=False))

    loop_exit_addr = cur_addr
    insns[exit_branch_idx] = struct.pack("<I", arm_branch(cave_addr + exit_branch_idx * 4, loop_exit_addr, link=False))

    # Restore registers and return to caller
    # pop {r4, r5, r6, r7, r8, sb, sl, lr}
    emit(0xE8BD4DF0)

    # Branch back to return address
    emit(arm_branch(cur_addr, return_addr, link=False))

    return b"".join(insns)
