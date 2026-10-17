# Pocket Kingdom: Mass-Sell Mod (N-Gage / EKA2L1)

Quality-of-life binary mod for *Pocket Kingdom: Own the World* that adds mass-selling of visible inventory items on the active shop page.

## How to Apply the Patch

1. Ensure Python 3 and Capstone are available:
   ```bash
   pip install capstone
   ```
2. Run the patcher script:
   ```bash
   python3 tools/patch_mass_sell.py System/Apps/6RAH/6RAH.APP
   ```
   *Note: An automatic backup (`6RAH.APP.orig`) is created prior to patching.*

3. Verify the binary modifications:
   ```bash
   python3 tools/verify_patch.py
   ```

4. Launch the game in **EKA2L1**:
   - Navigate to the Shop -> Sell menu.
   - Confirming a sale now processes all eligible items on the current screen.
