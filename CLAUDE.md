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

## Symbian / N-Gage Binary Architecture
- **Main Executable:** `System/Apps/6RAH/6RAH.APP`
  - Format: Symbian E32Image (uncompressed EPOC binary, CPU: 0x2000 / ARMv4T)
  - Code Base: `0x10000000`, Code Offset: `0x7C`
  - MultiBitmap Assets: `POKEKIN.MBM` (contains 488 bitmap sprites/UI elements)
  - Data Files: `System/Apps/6RAH/*.dat` and `System/Apps/6RAH/english/*.dat`
- **Testing Environment:** EKA2L1 Symbian Emulator on Windows host.
  - Windows share path: `\\wsl.localhost\archlinux\home\bossku\Pocket Kingdom\System\Apps\6RAH\6RAH.APP`

## Local Modding & Patching Tools
- **Patcher:** `python3 tools/patch_mass_sell.py [path_to_6RAH.APP]`
- **Verification:** `python3 tools/verify_patch.py`
- **Tests:** `PYTHONPATH=. python3 -m unittest discover tests`
