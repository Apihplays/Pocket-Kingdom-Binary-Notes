import unittest

from tools.build_unitdb import parse_material_detail, parse_materials

# Trimmed slice of the archived Material Database (2006-09-01): the section
# header rows are what carries each row's category.
FIXTURE = """
<table width="100%" class="TableBase">
<tr><td class="TableHead">Item</td><td align="center" class="TableHead">Rarity</td>
    <td align="center" class="TableHead">Effect</td></tr>
<tr><td colspan="6" class="TableHead"><b>Jewels</b></td></tr>
<tr><td class="TableCell1"><a href="view_material.phtml?id=63" class="TableCell1Link"><b>Garnet</b></a></td>
    <td class="TableCell1" align="center">2</td>
    <td class="TableCell1" align="center">Element: Fire</td></tr>
<tr><td class="TableCell2"><a href="view_material.phtml?id=82" class="TableCell2Link"><b>Topaz</b></a></td>
    <td class="TableCell2" align="center">8</td>
    <td class="TableCell2" align="center">Element: Earth</td></tr>
<tr><td colspan="6" class="TableHead"><b>Ores</b></td></tr>
<tr><td class="TableCell1"><a href="view_material.phtml?id=90" class="TableCell1Link"><b>Copper</b></a></td>
    <td class="TableCell1" align="center">1</td>
    <td class="TableCell1" align="center">-</td></tr>
<tr><td colspan="6" class="TableHead"><b>Other Materials</b></td></tr>
<tr><td class="TableCell1"><a href="view_material.phtml?id=75" class="TableCell1Link"><b>Cat's Eye</b></a></td>
    <td class="TableCell1" align="center">3</td>
    <td class="TableCell1" align="center">Element: Metal</td></tr>
</table>
"""


# Trimmed detail page: every section is a bold-titled table and any of them
# may be absent for a given material.
DETAIL_FIXTURE = """
<div style="font-family: Arial; font-size: 12pt; font-weight: bold; color: #000000;">COPPER</div>
<table width="100%" class="TableBase"><tr><td class="TableHead">Item</td></tr></table>
<div style="font-family: Arial; font-size: 12pt; font-weight: bold; color: #000000;">Purchase In</div>
<table width="100%" class="TableBase">
<tr><td width="100%" class="TableHead">Location</td></tr>
<tr valign="center"><td class="TableCell1">Elynotis</td></tr>
<tr valign="center"><td class="TableCell2">Cressence</td></tr>
</table>
<div style="font-family: Arial; font-size: 12pt; font-weight: bold; color: #000000;">Dropped By</div>
<table width="100%" class="TableBase">
<tr><td class="TableHead">#</td><td class="TableHead">Class</td><td class="TableHead">Race</td></tr>
<tr valign="center"><td class="TableCell1"><a href="/web/20060908144251/http://pk.warcry.com/units/view_unit.phtml?id=0">
    <img src="/gfx/race_icons/1.gif" alt="Unit 0"></a></td>
    <td class="TableCell1"><a href="view_unit.phtml?id=0" class="TableCell1Link"><b>Soldier</b></a></td>
    <td class="TableCell1">Warrior</td></tr>
</table>
<div style="font-family: Arial; font-size: 12pt; font-weight: bold; color: #000000;">Area Searches</div>
<table width="100%" class="TableBase">
<tr><td width="45%" class="TableHead">Area</td><td width="5%" class="TableHead">&nbsp;</td></tr>
<tr><td class="TableCell1">Elynotis</td><td class="TableCell1" align="center">Offline</td></tr>
<tr><td class="TableCell2">Cressence</td><td class="TableCell2" align="center">Online</td></tr>
</table>
<div style="font-family: Arial; font-size: 12pt; font-weight: bold; color: #000000;">Dungeon Reward</div>
<table width="100%" class="TableBase">
<tr><td class="TableHead">Dungeon</td><td class="TableHead">Area</td><td class="TableHead">Floors</td></tr>
<tr><td class="TableCell1">Castle Matres</td><td class="TableCell1">Elynotis</td>
    <td class="TableCell1" align="center">1</td></tr>
</table>
"""

BARE_FIXTURE = """
<div style="font-family: Arial; font-size: 12pt; font-weight: bold; color: #000000;">GAIA ROCK</div>
<table><tr><td class="TableHead">Item</td></tr></table>
"""


class TestParseMaterialDetail(unittest.TestCase):
    def setUp(self):
        self.detail = parse_material_detail(DETAIL_FIXTURE)

    def test_purchase_locations(self):
        self.assertEqual(self.detail["purchase_in"], ["Elynotis", "Cressence"])

    def test_dropped_by_units(self):
        self.assertEqual(self.detail["dropped_by"], [{"id": 0, "name": "Soldier"}])

    def test_area_searches(self):
        self.assertEqual(self.detail["area_searches"],
                         [{"area": "Elynotis", "status": "Offline"},
                          {"area": "Cressence", "status": "Online"}])

    def test_dungeon_reward(self):
        self.assertEqual(self.detail["dungeon_reward"],
                         [{"dungeon": "Castle Matres", "area": "Elynotis", "floors": 1}])

    def test_missing_sections_are_empty(self):
        self.assertEqual(parse_material_detail(BARE_FIXTURE),
                         {"purchase_in": [], "dropped_by": [],
                          "area_searches": [], "dungeon_reward": []})


class TestParseMaterials(unittest.TestCase):
    def setUp(self):
        self.rows = parse_materials(FIXTURE)

    def test_one_row_per_material(self):
        self.assertEqual(len(self.rows), 4)

    def test_section_headers_assign_category(self):
        self.assertEqual([r["category"] for r in self.rows],
                         ["Jewels", "Jewels", "Ores", "Other Materials"])

    def test_id_rarity_effect(self):
        garnet = self.rows[0]
        self.assertEqual(garnet, {"id": 63, "name": "Garnet", "category": "Jewels",
                                  "rarity": 2, "effect": "Element: Fire"})
        self.assertEqual(self.rows[2]["rarity"], 1)
        self.assertEqual(self.rows[2]["effect"], "-")

    def test_entities_unescaped(self):
        self.assertEqual(self.rows[3]["name"], "Cat's Eye")

    def test_header_row_is_not_a_material(self):
        self.assertNotIn("Item", [r["name"] for r in self.rows])


if __name__ == "__main__":
    unittest.main()
