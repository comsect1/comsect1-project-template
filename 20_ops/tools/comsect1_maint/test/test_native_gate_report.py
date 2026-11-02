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

    def valid(self, blocked=False):
        outcome = dict.fromkeys(COUNTS, 0)
        outcome.update(assessment_blocked=blocked, assessment_count=int(blocked))
        return {"verdict": "INDETERMINATE" if blocked else "PASS", "finding_count": int(blocked),
                "handoff": "BLOCK" if blocked else "CONTINUE",
                "findings": [{"code": "UNRESOLVED_OBSERVATION"}] if blocked else [], "outcome_summary": outcome}

    def test_consistent_reports(self):
        self.assertEqual(self.read(self.valid())["verdict"], "PASS")
        for verdict, code in (("FAIL", 3), ("INDETERMINATE", 4)):
            report = dict(self.valid(), verdict=verdict, handoff="BLOCK",
                          finding_count=1, findings=[{"code": "OBSERVED"}])
            self.assertEqual(self.read(report, code)["finding_codes"], {"OBSERVED": 1})
        lane = self.read(self.valid(True), 4)
        self.assertEqual((lane["finding_count"], lane["outcome_summary"]["assessment_count"]), (1, 1))

    def test_count_must_match_actual_findings(self):
        for report in (dict(self.valid(), findings=[{"code": "OBSERVED"}]),
                       dict(self.valid(), finding_count=-1)):
            with self.assertRaisesRegex(driver.ToolError, "finding count"):
                self.read(report)

    def test_pass_requires_continue(self):
        with self.assertRaisesRegex(driver.ToolError, "handoff"):
            self.read(dict(self.valid(), handoff="BLOCK"))

    def test_bool_is_not_a_count(self):
        with self.assertRaisesRegex(driver.ToolError, "member types"):
            self.read(dict(self.valid(), finding_count=False))

    def test_process_and_report_must_agree(self):
        for report, code in ((self.valid(), 4),
                             (dict(self.valid(), verdict="FAIL", handoff="BLOCK"), 0)):
            with self.assertRaisesRegex(driver.ToolError, "inconsistent"):
                self.read(report, code)

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
        for code in (2, -1, 99):
            with self.subTest(code=code), self.assertRaisesRegex(driver.ToolError, "member types"):
                self.read(self.valid(), code)

    def test_a_blocked_assessment_keeps_block(self):
        report = self.valid(True)
        report["handoff"] = "CONTINUE_WITH_RISK"
        with self.assertRaisesRegex(driver.ToolError, "blocking result"):
            self.read(report, 4)
        report = self.valid()
        report["outcome_summary"]["assessment_blocked"] = True
        with self.assertRaisesRegex(driver.ToolError, "blocked assessment"):
            self.read(report)

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
