import unittest

from tools.build_unitdb import parse_materials

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
