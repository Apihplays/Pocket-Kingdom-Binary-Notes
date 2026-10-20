"""Cross-table integrity for the generated database.

These read the committed outputs rather than the network, so they also catch a
builder change that silently breaks a join key.
"""

import json
import re
import unittest
from pathlib import Path

from tools.build_unitdb import INGREDIENT_ALIASES, WILDCARD_INGREDIENTS

DB = Path(__file__).resolve().parents[1] / "unitdb"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load(name: str):
    return json.loads((DB / name).read_text(encoding="utf-8"))


class TestIngredientLinks(unittest.TestCase):
    def setUp(self):
        self.material_keys = {norm(m["name"]) for m in load("materials.json")}
        self.recipes = load("crafting.json") + load("emblems.json")

    def key(self, value: str) -> str:
        k = norm(value)
        return INGREDIENT_ALIASES.get(k, k)

    def test_every_recipe_ingredient_resolves_to_a_material(self):
        unresolved = set()
        for recipe in self.recipes:
            for field in ("ore", "item1", "item2"):
                value = recipe[field]
                if norm(value) in WILDCARD_INGREDIENTS:
                    continue
                if self.key(value) not in self.material_keys:
                    unresolved.add(value)
        self.assertEqual(unresolved, set())

    def test_alias_targets_are_real_materials(self):
        self.assertLessEqual(set(INGREDIENT_ALIASES.values()), self.material_keys)

    def test_alias_is_actually_used(self):
        # Guards against deleting the recipe row the alias exists for.
        raw = {norm(r["item2"]) for r in self.recipes}
        self.assertTrue(set(INGREDIENT_ALIASES) & raw)


if __name__ == "__main__":
    unittest.main()
