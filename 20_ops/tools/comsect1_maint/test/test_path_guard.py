# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""path_guard: every original component is checked before canonicalization (moved from WSB/Sunset)."""
import os
from pathlib import Path
import unittest
from unittest import mock

import maint_support as support

guard = support.package_module("path_guard")


class PathGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("path_guard")

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def setUp(self):
        self.root = self.work.folder(self._testMethodName)

    def test_dotdot_checks_the_cancelled_component(self):
        membrane = self.root / "sdk" / "membrane"
        membrane.mkdir(parents=True)
        contract = support.write(self.root / "sdk" / "contract" / "header.h", "/* h */\n")
        raw = membrane / ".." / "contract" / "header.h"
        self.assertEqual(guard.checked_path(raw), contract.resolve())
        original = guard.os.path.isjunction
        with mock.patch.object(guard.os.path, "isjunction", side_effect=lambda p: Path(p) == membrane or original(p)):
            with self.assertRaisesRegex(ValueError, "reparse"):
                guard.checked_path(raw)

    def test_file_cannot_be_cancelled_by_dotdot(self):
        leaf = support.write(self.root / "sdk" / "file", "x\n")
        support.write(self.root / "sdk" / "header.h", "x\n")
        with self.assertRaisesRegex(ValueError, "non-directory"):
            guard.checked_path(leaf / ".." / "header.h")

    def test_anchor_is_checked(self):
        header = support.write(self.root / "header.h", "x\n")
        anchor = Path(header.anchor)
        original = guard.os.path.isjunction
        with mock.patch.object(guard.os.path, "isjunction", side_effect=lambda p: Path(p) == anchor or original(p)):
            with self.assertRaisesRegex(ValueError, "reparse"):
                guard.checked_path(header)

    @unittest.skipUnless(os.name == "nt", "Windows path semantics")
    def test_ambiguous_windows_paths_are_refused(self):
        for raw in (self.root.drive + "relative.h", chr(92) + "relative.h"):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "ambiguous"):
                guard.checked_path(raw)


if __name__ == "__main__":
    unittest.main()
