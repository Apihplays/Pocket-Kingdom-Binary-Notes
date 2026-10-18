"""Locating the user's Pocket Kingdom install for tests.

This repo ships no game assets. Tests that need them look in
``$PK_GAME_DIR`` (default: ``System/Apps/6RAH``) and are skipped when the
install is not present.
"""

import os
import unittest

GAME_DIR = os.environ.get("PK_GAME_DIR", "System/Apps/6RAH")
APP = os.path.join(GAME_DIR, "6RAH.APP")
APP_ORIG = APP + ".orig"


def app_binary() -> str:
    """Prefer the pristine backup when present, else the live binary."""
    return APP_ORIG if os.path.exists(APP_ORIG) else APP


def has_game() -> bool:
    return os.path.exists(APP)


def has_data() -> bool:
    return bool(__import__("glob").glob(os.path.join(GAME_DIR, "comp*.dat")))


needs_game = unittest.skipUnless(
    has_game(), f"no game install at {GAME_DIR!r}; set PK_GAME_DIR to your own copy"
)
needs_data = unittest.skipUnless(
    has_data(), f"no data files at {GAME_DIR!r}; set PK_GAME_DIR to your own copy"
)
