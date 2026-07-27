import copy
import unittest

from incident_evidence_timeline import TimelineInputError, build_timeline


def fixture():
    return {
        "incident_id": "INC-2042",
        "gap_threshold_seconds": 300,
        "sources": [
            {"name": "cloudwatch", "clock_offset_seconds": 0},
            {"name": "deploy", "clock_offset_seconds": 30},
        ],
        "events": [
            {"id": "d1", "source": "deploy", "timestamp": "2026-07-27T14:00:30Z", "severity": "info", "service": "api", "type": "deployment", "message": "Release started"},
            {"id": "m1", "source": "cloudwatch", "timestamp": "2026-07-27T14:01:00Z", "severity": "error", "service": "api", "type": "alarm", "message": "Error rate increased"},
        ],
    }


class BuildTimelineTests(unittest.TestCase):
    def test_orders_events_after_clock_correction(self):
        report = build_timeline(fixture())
        self.assertEqual(["d1", "m1"], [event["id"] for event in report["timeline"]])
        self.assertEqual("2026-07-27T14:00:00Z", report["timeline"][0]["normalized_at"])

    def test_ready_without_evidence_gap(self):
        self.assertEqual("READY", build_timeline(fixture())["decision"])

    def test_large_gap_requires_review(self):
        data = fixture()
        data["events"][1]["timestamp"] = "2026-07-27T14:12:00Z"
        report = build_timeline(data)
        self.assertEqual("REVIEW", report["decision"])
        self.assertEqual(720, report["gaps"][0]["gap_seconds"])

    def test_exact_duplicate_is_removed(self):
        data = fixture()
        data["events"].append(copy.deepcopy(data["events"][0]))
        report = build_timeline(data)
        self.assertEqual(1, report["duplicate_count"])
        self.assertEqual(2, report["event_count"])

    def test_conflicting_duplicate_fails_closed(self):
        data = fixture()
        conflict = copy.deepcopy(data["events"][0])
        conflict["message"] = "Different evidence"
        data["events"].append(conflict)
        with self.assertRaises(TimelineInputError):
            build_timeline(data)

    def test_unknown_source_fails_closed(self):
        data = fixture()
        data["events"][0]["source"] = "unknown"
        with self.assertRaises(TimelineInputError):
            build_timeline(data)

    def test_timezone_is_required(self):
        data = fixture()
        data["events"][0]["timestamp"] = "2026-07-27T14:00:30"
        with self.assertRaises(TimelineInputError):
            build_timeline(data)

    def test_invalid_severity_fails_closed(self):
        data = fixture()
        data["events"][0]["severity"] = "urgent"
        with self.assertRaises(TimelineInputError):
            build_timeline(data)

    def test_input_is_not_mutated_and_result_is_deterministic(self):
        data = fixture()
        original = copy.deepcopy(data)
        self.assertEqual(build_timeline(data), build_timeline(data))
        self.assertEqual(original, data)

    def test_safety_boundary_is_explicit(self):
        safety = build_timeline(fixture())["safety"]
        self.assertTrue(safety["read_only"])
        self.assertFalse(safety["external_calls"])
        self.assertFalse(safety["changes_infrastructure"])


if __name__ == "__main__":
    unittest.main()

