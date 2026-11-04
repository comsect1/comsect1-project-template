# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Gate report boundary checks (moved from WSB/Sunset, with DCB's outcome_summary cases); no process."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import maint_support as support

driver = support.package_module("native_gate")
COUNTS = ("assessment_count", "debt_count", "limit_count", "notice_count", "rework_count", "violation_count")


class GateReportTests(unittest.TestCase):
    def read(self, report, code=0):
        raw = report if isinstance(report, str) else json.dumps(report)
        with patch.object(Path, "is_file", return_value=True), \
                patch.object(Path, "read_text", return_value=raw), \
                patch.object(driver, "sha256_file", return_value="a" * 64):
            return driver.read_report(Path("mock-report.json"), "", code)

    def valid(self, verdict="PASS"):
        """A consistent report of the verdict: INDETERMINATE has one unassessed site, FAIL one violation."""
        outcome = dict.fromkeys(COUNTS, 0)
        assessment = {"reasons": {}, "missing_capabilities": [], "unassessed_site_count": 0}
        findings = []
        if verdict == "INDETERMINATE":
            outcome.update(assessment_blocked=True, assessment_count=1)
            assessment = {"reasons": {"UNKNOWN_TARGET": 1}, "missing_capabilities": ["language-provider.c"],
                          "unassessed_site_count": 1}
            findings = [{"code": "UNRESOLVED_OBSERVATION"}]
        else:
            outcome.update(assessment_blocked=False)
        if verdict == "FAIL":
            outcome.update(violation_count=1)
            findings = [{"code": "OBSERVED"}]
        if verdict in ("WARN", "REQ"):
            outcome.update(rework_count=1)
            findings = [{"code": "OBSERVED"}]
        return {"verdict": verdict, "finding_count": len(findings), "handoff": driver.VERDICT_HANDOFF[verdict],
                "findings": findings, "outcome_summary": outcome, "assessment": assessment}

    def test_every_verdict_has_its_handoff_and_exit(self):
        for verdict, handoff, code in (("PASS", "CONTINUE", 0), ("WARN", "CONTINUE_WITH_RISK", 0),
                                       ("REQ", "CONTINUE_WITH_RISK", 0),
                                       ("INDETERMINATE", "CONTINUE_WITH_RISK", 0), ("FAIL", "BLOCK", 1)):
            with self.subTest(verdict=verdict):
                lane = self.read(self.valid(verdict), code)
                self.assertEqual((lane["verdict"], lane["handoff"], lane["gate_exit"]), (verdict, handoff, code))
                self.assertEqual(driver.verdict_exit(verdict), driver.EXIT_FAIL if verdict == "FAIL" else 0)
        self.assertFalse(hasattr(driver, "EXIT_INDETERMINATE"))
        self.assertNotIn(3, driver.EXIT_NAMES)

    def test_an_incomplete_assessment_continues_and_is_recorded(self):
        lane = self.read(self.valid("INDETERMINATE"), 0)
        self.assertEqual((lane["finding_count"], lane["outcome_summary"]["assessment_count"],
                          lane["outcome_summary"]["violation_count"]), (1, 1, 0))
        self.assertEqual(lane["assessment"], {"reasons": {"UNKNOWN_TARGET": 1},
                                              "missing_capabilities": ["language-provider.c"],
                                              "unassessed_site_count": 1})
        self.assertEqual(driver.verdict_exit(lane["verdict"]), driver.EXIT_CONTINUE)
        line = driver.lane_line("native", lane)
        self.assertIn("handoff=CONTINUE_WITH_RISK gate_exit=0 violations=0", line)
        self.assertIn("unassessed_sites=1 reasons=UNKNOWN_TARGET:1 missing_capabilities=language-provider.c", line)

    def test_blocking_follows_violations_only(self):
        for verdict, code, change in (("INDETERMINATE", 0, {"handoff": "BLOCK"}),
                                      ("FAIL", 1, {"handoff": "CONTINUE_WITH_RISK"}),
                                      ("PASS", 0, {"handoff": "BLOCK"})):
            with self.subTest(verdict=verdict, change=change), self.assertRaisesRegex(driver.ToolError, "handoff"):
                self.read(dict(self.valid(verdict), **change), code)
        no_violation = self.valid("FAIL")
        no_violation["outcome_summary"]["violation_count"] = 0
        with self.assertRaisesRegex(driver.ToolError, "violations"):
            self.read(no_violation, 1)
        hidden = self.valid("INDETERMINATE")
        hidden["outcome_summary"]["violation_count"] = 1
        with self.assertRaisesRegex(driver.ToolError, "violations"):
            self.read(hidden, 0)

    def test_count_must_match_actual_findings(self):
        for report in (dict(self.valid(), findings=[{"code": "OBSERVED"}]),
                       dict(self.valid(), finding_count=-1)):
            with self.assertRaisesRegex(driver.ToolError, "finding count"):
                self.read(report)

    def test_pass_requires_continue_and_no_findings(self):
        with self.assertRaisesRegex(driver.ToolError, "handoff"):
            self.read(dict(self.valid(), handoff="CONTINUE_WITH_RISK"))
        with self.assertRaisesRegex(driver.ToolError, "PASS with 1 findings"):
            self.read(dict(self.valid(), finding_count=1, findings=[{"code": "OBSERVED"}]))

    def test_bool_is_not_a_count(self):
        with self.assertRaisesRegex(driver.ToolError, "member types"):
            self.read(dict(self.valid(), finding_count=False))

    def test_process_and_report_must_agree(self):
        for report, code in ((self.valid(), 1), (self.valid("INDETERMINATE"), 1), (self.valid("FAIL"), 0)):
            with self.subTest(verdict=report["verdict"], code=code), self.assertRaisesRegex(driver.ToolError, "inconsistent"):
                self.read(report, code)

    def test_retired_and_error_exits_are_refused(self):
        for code in (2, 3, 4, -1, 99, True):
            with self.subTest(code=code), self.assertRaisesRegex(driver.ToolError, "member types"):
                self.read(self.valid("INDETERMINATE"), code)

    def test_outcome_summary_is_required_and_strict(self):
        for key, value in (("verdict", "UNKNOWN"), ("handoff", "LATER"), ("outcome_summary", {}),
                           ("outcome_summary", None)):
            bad = dict(self.valid(), **{key: value})
            with self.subTest(key=key, value=value), self.assertRaisesRegex(driver.ToolError, "member types"):
                self.read(bad)
        for key in COUNTS + ("assessment_blocked",):
            bad = copy.deepcopy(self.valid())
            del bad["outcome_summary"][key]
            with self.subTest(missing=key), self.assertRaisesRegex(driver.ToolError, "member types"):
                self.read(bad)

    def test_assessment_member_is_required_and_strict(self):
        bad_values = (None, [], {}, {"reasons": {}, "missing_capabilities": []},
                      {"reasons": [], "missing_capabilities": [], "unassessed_site_count": 0},
                      {"reasons": {"X": True}, "missing_capabilities": [], "unassessed_site_count": 0},
                      {"reasons": {}, "missing_capabilities": [1], "unassessed_site_count": 0},
                      {"reasons": {}, "missing_capabilities": [], "unassessed_site_count": -1},
                      {"reasons": {}, "missing_capabilities": [], "unassessed_site_count": 0, "extra": 1})
        for value in bad_values:
            bad = dict(self.valid(), assessment=value)
            with self.subTest(value=value), self.assertRaisesRegex(driver.ToolError, "assessment member"):
                self.read(bad)
        missing = self.valid()
        del missing["assessment"]
        with self.assertRaisesRegex(driver.ToolError, "assessment member"):
            self.read(missing)

    def test_ambiguous_or_nonfinite_json_is_refused(self):
        raw = json.dumps(self.valid())
        for invalid in ('{"verdict":"FAIL",' + raw[1:],
                        raw[:-1] + ',"extra":NaN}',
                        raw[:-1] + ',"extra":Infinity}',
                        raw[:-1] + ',"extra":{"key":0,"key":1}}'):
            with self.subTest(raw=invalid), self.assertRaisesRegex(driver.ToolError, "Gate report unusable"):
                self.read(invalid)

    def test_missing_or_malformed_report_is_refused(self):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(driver.ToolError, "no report"):
                driver.read_report(Path("mock-missing.json"), "failed", 2)
        for raw in ("[]", "{}", "not-json"):
            with self.assertRaisesRegex(driver.ToolError, "Gate report unusable"):
                self.read(raw)


if __name__ == "__main__":
    unittest.main()
