import datetime as dt
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import check_backup as gate
except ZoneInfoNotFoundError:
    gate = None


@unittest.skipIf(gate is None, "IANA timezone data unavailable")
class BackupTests(unittest.TestCase):
    def test_new_york_schedule_across_dst(self):
        for day, utc_hours in [
            (dt.date(2026, 3, 7), (8, 11)),
            (dt.date(2026, 3, 8), (7, 10)),
            (dt.date(2026, 10, 31), (7, 10)),
            (dt.date(2026, 11, 1), (8, 11)),
        ]:
            with self.subTest(day=day):
                self.assertEqual(tuple(
                    dt.datetime.combine(day, dt.time(hour), gate.EASTERN)
                    .astimezone(dt.timezone.utc).hour for hour in (3, 6)
                ), utc_hours)

    def test_only_verified_success_of_todays_overnight_refresh_suppresses_backup(self):
        day = dt.date(2026, 11, 5)
        run = dict(id=1, event="schedule", head_branch="main",
                   display_title=gate.OVERNIGHT_TITLE, status="completed",
                   conclusion="success", created_at="2026-11-05T08:00:00Z")
        self.assertTrue(gate.overnight_succeeded([run], day, lambda _: True))
        self.assertFalse(gate.overnight_succeeded([run], day, lambda _: False))
        self.assertFalse(gate.overnight_succeeded([], day, lambda _: True))
        for change in (
            {"conclusion": "failure"}, {"status": "in_progress"},
            {"event": "workflow_dispatch"}, {"head_branch": "candidate"},
            {"display_title": "Discovery backup (6 a.m. Eastern)"},
            {"created_at": "2026-11-05T04:59:59Z"},
        ):
            with self.subTest(change=change):
                self.assertFalse(gate.overnight_succeeded(
                    [run | change], day, lambda _: True))
