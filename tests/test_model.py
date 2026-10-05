"""Manual-derived assembly regressions. These tests never import or launch Blender."""

import copy
import math
from types import SimpleNamespace
import unittest
from bear_basin.hardware import nut_for, nut_mass_kg
from bear_basin.joints import build_joints
from bear_basin.shapes import floorboard_outline, polygon_area, socket_miter_frame
from bear_basin.validation import (
    validate_records,
    interval_overlap,
    interval_gap,
    line_intervals,
)


def point(x, y):
    return SimpleNamespace(x=x, y=y)


def part(code, x=0, y0=-1, y1=1):
    return dict(code=code, p0=point(x, y0), p1=point(x, y1))


class ManualAssemblyTests(unittest.TestCase):
    def schedule(self, members):
        return build_joints(
            SimpleNamespace(members=members, net_fixings=[], floor_support_y=1)
        )

    def supports(self, schedule, member):
        return {
            base: count
            for _, attached, base, _, count in schedule
            if attached == member
        }

    def test_floorboard_schedule_matches_steps_65_through_71(self):
        members = {
            "W01_7": part("W01", -0.3, -0.25, 0.25),
            "W01_14": part("W01", 0.3, -0.25, 0.25),
            "W02_7_F": part("W02", -0.3, -1, -0.27),
            "W02_7_B": part("W02", -0.3, 0.27, 1),
            "W10_10": part("W10", -0.05),
        }
        joints = self.schedule(members)
        self.assertEqual(
            self.supports(joints, "W01_7"), {"KA11_C": 1, "CA10_0_F": 1, "CA10_0_B": 1}
        )
        self.assertEqual(
            self.supports(joints, "W01_14"), {"KA11_C": 1, "CA10_1_F": 1, "CA10_1_B": 1}
        )
        self.assertEqual(
            self.supports(joints, "W02_7_F"), {"K06": 1, "K05_F": 1, "KA11_F": 1}
        )
        self.assertEqual(
            self.supports(joints, "W02_7_B"), {"K07": 1, "K05_B": 1, "KA11_B": 1}
        )
        self.assertEqual(
            self.supports(joints, "W10_10"),
            {"K06": 1, "K05_F": 2, "K05_B": 2, "K07": 1},
        )

    def test_small_deck_edge_boards_have_six_screws(self):
        schedule = self.schedule(
            {"W12A_sd0": part("W12A"), "W12_sd10": part("W12"), "W08_sd1": part("W08")}
        )
        for name in ("W12A_sd0", "W12_sd10"):
            self.assertEqual(
                sum(n for _, a, _, t, n in schedule if a == name and t == "SW35"), 6
            )
        self.assertEqual(
            sum(n for _, a, _, t, n in schedule if a == "W08_sd1" and t == "SW35"), 5
        )

    def test_tarp_has_six_screws_per_eave(self):
        joints = [j for j in self.schedule({}) if j[1] == "Tarp"]
        self.assertEqual(len(joints), 4)
        self.assertEqual({j[2] for j in joints}, {"F16_B", "F16_F", "F16_W", "F16_E"})
        self.assertTrue(all(j[3:] == ("SW16", 6) for j in joints))

    def test_ladder_screws_enter_uprights_and_reach_rung_ends(self):
        joints = [joint for joint in self.schedule({}) if joint[0] == 104]
        self.assertEqual(len(joints), 8)
        self.assertEqual({joint[1] for joint in joints}, {"K20", "K21"})
        self.assertEqual({joint[2] for joint in joints}, {f"F23_{i}" for i in range(4)})
        self.assertTrue(all(joint[3:] == ("SW50", 2) for joint in joints))

    def test_net_nuts_follow_assembly_instructions(self):
        for step in (175, 176, 177, 178):
            self.assertEqual(nut_for(step, "EYE", "eye", "leg"), ["BM818"])
        self.assertEqual(nut_for(182, "M833", "eye", "rail"), ["BM818"])
        self.assertEqual(nut_for(183, "M821", "eye", "rail"), ["BM818"])
        self.assertEqual(nut_for(14, "M896", "board", "leg"), ["NM815"])

    def test_notched_boards_retain_rail_support_and_remove_leg_corners(self):
        width, extent = 0.089, 1.03
        left = floorboard_outline(-0.05, width, extent, 0.038, 0.918)
        right = floorboard_outline(0.05, width, extent, 0.038, 0.918)
        self.assertEqual(max(y for x, y in right), extent)
        self.assertEqual(min(y for x, y in right), -extent)
        self.assertTrue(all(x >= 0.038 for x, y in right if abs(y) == extent))
        self.assertAlmostEqual(polygon_area(left), polygon_area(right))
        self.assertLess(polygon_area(right), width * extent * 2)
        self.assertGreater(polygon_area(right), width * 1.8)


class RecordValidationTests(unittest.TestCase):
    def setUp(self):
        self.members = {"plate": {"mass": 0.2}, "beam": {"mass": 2}}
        self.joints = [(159, "plate", "beam", "HANGER", 1)]
        self.fasteners = [
            dict(
                id="joint_0000_0",
                joint_id="joint_0000",
                step=159,
                attached="plate",
                base="beam",
                type="HANGER",
                pos=[0, 0, 1],
                axis=[0, 0, 1],
            )
        ]
        self.nuts = [
            dict(fastener_id="joint_0000_0", type=kind, side=side)
            for kind, side in [
                ("Washer", "head"),
                ("Washer", "base"),
                ("LockNut", "base"),
            ]
        ]

    def result(self):
        return validate_records(self.members, self.joints, self.fasteners, self.nuts)

    def test_valid_hanger_requires_washers_on_both_sides(self):
        self.assertEqual(self.result()["errors"], [])
        self.nuts.pop(0)
        self.assertTrue(any("stack" in e for e in self.result()["errors"]))

    def test_count_duplicate_identity_and_unknown_reference_fail(self):
        self.fasteners.append(copy.deepcopy(self.fasteners[0]))
        errors = self.result()["errors"]
        self.assertTrue(any("Duplicate" in e for e in errors))
        self.assertTrue(any("expected 1, placed 2" in e for e in errors))
        del self.members["beam"]
        self.assertTrue(any("unknown member" in e for e in self.result()["errors"]))

    def test_nonfinite_coordinates_and_nonunit_axis_fail(self):
        self.fasteners[0]["pos"][0] = math.nan
        self.fasteners[0]["axis"] = [0, 0, 2]
        errors = self.result()["errors"]
        self.assertTrue(any("invalid pos" in e for e in errors))
        self.assertTrue(any("unit vector" in e for e in errors))

    def test_wrong_assignment_cannot_pass_with_the_right_count(self):
        self.fasteners[0]["base"] = "plate"
        self.assertTrue(
            any("assignment differs" in error for error in self.result()["errors"])
        )

    def test_inventory_difference_is_reported_not_filled(self):
        result = self.result()
        self.assertEqual(result["inventory"]["Washer"]["modeled"], 2)
        self.assertEqual(result["inventory"]["Washer"]["manual"], 8)
        self.assertEqual(result["errors"], [])
        self.assertGreater(nut_mass_kg("Washer"), 0)


class BracketJoinTests(unittest.TestCase):
    def test_miter_is_flush_without_widening_the_socket(self):
        angle, qz = socket_miter_frame(.039, 1.812, .039, .97)
        for offset in (-.039, 0, .039):
            travel = -offset / math.tan(angle)
            y = .039 + offset * math.cos(angle) + travel * math.sin(angle)
            self.assertAlmostEqual(y, .039)
            # Projection back onto the cross-section retains the original width.
            z = qz + offset * math.sin(angle) - travel * math.cos(angle)
            recovered = (y - .039) * math.cos(angle) + (z - qz) * math.sin(angle)
            self.assertAlmostEqual(recovered, offset)
        self.assertAlmostEqual(qz - .039 / math.sin(angle), 1.812)
        self.assertAlmostEqual(.039 + qz * math.tan(angle), .97)

    def test_invalid_socket_fit_fails(self):
        for dimensions in [(1, 2, .04, .9), (.04, -2, .04, .9), (.04, 2, 0, .9)]:
            with self.assertRaises(ValueError):
                socket_miter_frame(*dimensions)


class MeshIntervalTests(unittest.TestCase):
    class Ray:
        """One-dimensional closed mesh analogue; no Blender dependency."""

        def __init__(self, crossings):
            self.crossings = crossings

        def ray_cast(self, origin, direction, distance):
            hits = [
                (point - origin) / direction
                for point in self.crossings
                if 0 <= (point - origin) / direction <= distance
            ]
            if not hits:
                return None, None, None, None
            travel = min(hits)
            return origin + direction * travel, None, None, travel

    def test_fully_embedded_shank_intersects_material(self):
        spans = line_intervals(self.Ray([-1.0, 1.0]), 0.0, 1.0, 2.0)
        self.assertEqual(spans, [(-1, 1)])
        self.assertTrue(interval_overlap(spans[0], 0, 0.05))

    def test_contact_gap_distinguishes_air_from_touching(self):
        self.assertAlmostEqual(interval_gap([(0, 0.03)], [(0.04, 0.1)]), 0.01)
        self.assertEqual(interval_gap([(0, 0.03)], [(0.03, 0.1)]), 0)
        self.assertEqual(interval_gap([(0, 0.04)], [(0.03, 0.1)]), 0)

    def test_open_fabric_is_a_surface_not_a_closed_solid(self):
        spans = line_intervals(self.Ray([0.02]), 0.0, 1.0, 1.0, sheet=True)
        self.assertAlmostEqual(spans[0][0], 0.02)
        self.assertEqual(spans[0][0], spans[0][1])
        with self.assertRaisesRegex(ValueError, "odd number"):
            line_intervals(self.Ray([0.02]), 0.0, 1.0, 1.0)


if __name__ == "__main__":
    unittest.main()
