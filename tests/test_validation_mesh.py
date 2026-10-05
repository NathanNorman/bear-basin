"""Independent closed-shell, engagement, and nut reach acceptance checks."""

import unittest

from bear_basin.validation import (
    connected_face_components, nut_reached, path_issues, union_intervals,
)


class SolidUnionTests(unittest.TestCase):
    def test_overlapping_solids_do_not_become_a_hole(self):
        self.assertEqual(union_intervals([(0, .03), (.02, .05)]), [(0, .05)])
        self.assertEqual(union_intervals([(0, .05), (.02, .03)]), [(0, .05)])

    def test_distinct_solids_retain_air_gap(self):
        self.assertEqual(union_intervals([(0, .01), (.02, .03)]), [(0, .01), (.02, .03)])

    def test_joined_mesh_keeps_disconnected_shells(self):
        faces = [(0, 1, 2), (2, 3, 0), (4, 5, 6), (6, 7, 4)]
        self.assertEqual(connected_face_components(faces), [faces[:2], faces[2:]])


class EngagementTests(unittest.TestCase):
    def test_regular_seated_joint(self):
        self.assertEqual(path_issues([(0, .03)], [(.03, .08)], .05, .006), [])

    def test_near_tip_contact_is_not_engagement(self):
        self.assertTrue(any("engagement" in reason for reason in
                            path_issues([(0, .03)], [(.049, .08)], .05, .006)))

    def test_buried_head_and_disconnected_material_fail(self):
        self.assertTrue(any("entry" in reason for reason in
                            path_issues([(-.02, .03)], [(.03, .08)], .05, .006)))
        self.assertTrue(any("continuous" in reason for reason in
                            path_issues([(0, .005), (.029, .035)], [(.035, .08)], .06, .006)))

    def test_fabric_seating_is_a_surface_not_solid_penetration(self):
        self.assertEqual(path_issues([(0, 0)], [(.002, .05)], .016, .004, sheet=True), [])
        self.assertEqual(path_issues([(-1e-7, -1e-7)], [(.002, .05)], .016, .004, sheet=True), [])
        self.assertTrue(path_issues([(0, 0)], [(.002, .05)], .016, .004))


class NutReachTests(unittest.TestCase):
    def test_barrel_can_reach_bolt_ending_before_far_face(self):
        self.assertTrue(nut_reached("BM825", .05, .033))
        self.assertFalse(nut_reached("NM815", .05, .033))

    def test_locknut_requires_actual_overlap(self):
        self.assertTrue(nut_reached("LockNut", .145, .16))
        self.assertFalse(nut_reached("LockNut", .159, .16))

    def test_washer_requires_bolt_through_its_thickness(self):
        self.assertTrue(nut_reached("Washer", .145, .16))
        self.assertFalse(nut_reached("Washer", .159, .16))


if __name__ == "__main__":
    unittest.main()
