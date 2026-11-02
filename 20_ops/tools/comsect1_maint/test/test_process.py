# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""process: link refusal, checked paths, the exact-run quarantine and the process timeout."""
import os
import sys
import unittest
from unittest import mock

import maint_support as support

process = support.process


class ProcessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("process")

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def test_absent_path_is_no_link_and_repo_paths_check(self):
        self.assertFalse(process.is_link(str(self.work.path / "absent")))
        self.assertEqual(process.checked_path(str(self.work.path)), os.path.abspath(str(self.work.path)))

    def test_outside_repository_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "outside"):
            process.checked_path(str(support.REPO_ROOT.parent / "outside" / "run"))

    def test_linked_ancestor_is_refused(self):
        linked = os.path.join(str(support.REPO_ROOT), "90_temps", "verification")
        with mock.patch.object(process, "is_link", side_effect=lambda p: os.path.normcase(p) == os.path.normcase(linked)):
            with self.assertRaisesRegex(RuntimeError, "linked"):
                process.checked_path(str(self.work.path / "x"))

    def test_quarantine_moves_only_the_exact_run(self):
        target = self.work.folder("quarantine_ok")
        support.write(target / "a" / "b.txt", "content\n")
        other = self.work.folder("quarantine_other")
        with mock.patch.object(process.os, "rename") as rename:
            with self.assertRaises(RuntimeError):
                process.quarantine(str(other), str(target), "never_" + self.work.run_id, str(support.REPO_ROOT))
        rename.assert_not_called()
        lines = []
        process.quarantine(str(target), str(target), "process_test_" + self.work.run_id, str(support.REPO_ROOT),
                           announce=lines.append, prune_levels=0)
        self.assertFalse(target.exists())
        self.assertFalse((support.REPO_ROOT / "99_trash" / ("process_test_" + self.work.run_id)).exists())
        self.assertIn("entries=2", lines[0])

    def test_linked_child_blocks_inventory(self):
        root = str(self.work.path)
        child = os.path.join(root, "linked")
        with mock.patch.object(process.os, "walk", return_value=[(root, ["linked"], [])]), \
                mock.patch.object(process, "is_link", side_effect=lambda path: path == child):
            with self.assertRaisesRegex(RuntimeError, "linked"):
                process.check_tree(root)

    def test_run_process_kills_the_tree_on_timeout(self):
        script = support.FIXTURES / "process" / "sleep_child.py"
        log = self.work.path / "timeout.txt"
        with self.assertRaises(process.ProcessError) as caught:
            process.run_process("sleeper", [sys.executable, "-I", "-B", script], 2, self.work.path, log)
        self.assertEqual(caught.exception.kind, "timeout")
        self.assertIn("process tree killed", log.read_text(encoding="utf-8"))

    def test_run_process_start_failure_and_output(self):
        with self.assertRaises(process.ProcessError) as caught:
            process.run_process("absent", [str(self.work.path / "absent.exe")], 5, self.work.path)
        self.assertEqual(caught.exception.kind, "start")
        code, out, _ = process.run_process("echo", [sys.executable, "-I", "-B", "-c", "import sys; sys.stdout.buffer.write(chr(233).encode('utf-8'))"], 30, self.work.path)
        self.assertEqual((code, out.strip()), (0, "é"))

    def test_run_id_and_digests(self):
        self.assertIsNotNone(process.RUN_ID_PATTERN.fullmatch(process.new_run_id("x")))
        self.assertEqual(process.sha256_text("a"), "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb")


if __name__ == "__main__":
    unittest.main()
