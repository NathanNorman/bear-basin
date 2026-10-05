"""Geometric path requirements independent of Blender and its BVH machinery."""

import unittest

from bear_basin.mesh_placement import material_path, ray_spans


class MaterialPathTests(unittest.TestCase):
    def test_seated_path_has_real_base_penetration(self):
        self.assertTrue(material_path([(0, .030)], [(.030, .060)], .050, .003))
        self.assertFalse(material_path([(0, .030)], [(.049, .060)], .050, .003))

    def test_buried_head_is_not_seated(self):
        self.assertFalse(material_path([(-.020, .030)], [(.030, .060)], .050, .003))

    def test_air_gap_is_not_hidden_by_intersecting_both_parts(self):
        self.assertFalse(material_path([(0, .020)], [(.030, .060)], .050, .003))

    def test_material_outside_shank_does_not_count(self):
        self.assertFalse(material_path([(0, .020)], [(-.040, -.010)], .050, .003))
        self.assertFalse(material_path([(0, .020)], [(.060, .080)], .050, .003))

    def test_disconnected_attached_island_does_not_bridge_air(self):
        self.assertFalse(material_path([(0, .005), (.029, .035)], [(.035, .08)], .060, .003))

    def test_thin_plate_is_permitted_and_point_contact_is_not(self):
        self.assertTrue(material_path([(0, .003)], [(.003, .080)], .050, .004))
        self.assertFalse(material_path([(0, 0)], [(0, .080)], .050, .004))

    def test_open_mesh_trace_is_not_accepted_as_solid(self):
        class Ray:
            def __init__(self, points):
                self.points = points

            def ray_cast(self, origin, axis, distance):
                hits = [(p-origin)/axis for p in self.points if 0 <= (p-origin)/axis <= distance]
                if not hits:
                    return None, None, None, None
                travel = min(hits)
                return origin + axis*travel, None, None, travel

        self.assertIsNone(ray_spans(Ray([.01]), 0, 1, 1))
        spans = ray_spans(Ray([-.02, .03]), 0, 1, 1)
        self.assertEqual(len(spans), 1)
        self.assertAlmostEqual(spans[0][0], -.02)
        self.assertAlmostEqual(spans[0][1], .03)


if __name__ == "__main__":
    unittest.main()
