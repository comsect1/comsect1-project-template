# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""cross_build: Cell selection and the size and symbol parsers (no toolchain run)."""
import unittest

import maint_support as support

cross = support.package_module("cross_build")


class CrossBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("cross_build")
        root = cls.work.folder("product")
        for path in ("engine", "platform/windows", "provider/serial"):
            support.c_cell(root, path, "dcb")
        cells = {"engine": support.c_entry("engine", ("windows", "arm")),
                 "windows": support.c_entry("platform/windows", freestanding=False),
                 "serial": support.c_entry("provider/serial", ("windows", "arm"),
                                           budget={"cortex-m4": {"text": 9, "data": 0, "bss": 0}})}
        cls.settings = support.product(root, "dcb", cells)

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def test_every_freestanding_arm_cell_is_selected(self):
        cores, cells = cross.selected_cells(None, self.settings)
        self.assertEqual([cell.name for cell in cells], ["engine", "serial"])
        self.assertEqual(cores, {"cortex-m4": ["-mthumb"]})
        self.assertEqual([cell.name for cell in cross.selected_cells("serial", self.settings)[1]], ["serial"])

    def test_unknown_or_hosted_cell_is_refused(self):
        with self.assertRaisesRegex(cross.CrossBuildError, "unknown Cell"):
            cross.selected_cells("absent", self.settings)
        with self.assertRaisesRegex(cross.CrossBuildError, "no freestanding Cell"):
            cross.selected_cells("windows", self.settings)

    def test_parsers(self):
        self.assertEqual(cross.parse_size("   text    data     bss     dec     hex filename\n"
                                          "     12       4       8      24      18 o.o\n"), (12, 4, 8))
        with self.assertRaises(cross.CrossBuildError):
            cross.parse_size("garbage\n")
        self.assertEqual(cross.parse_names("         U memcpy\n         U abs\n\n"), ["abs", "memcpy"])
        self.assertIsNotNone(cross.RUN_ID_PATTERN.fullmatch(cross.new_run_id()))


if __name__ == "__main__":
    unittest.main()
