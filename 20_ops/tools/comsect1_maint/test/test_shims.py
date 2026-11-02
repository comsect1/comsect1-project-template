# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Each entry shim exposes the names of its package module (the same objects), loaded by file path."""
import unittest

import maint_support as support


class ShimTest(unittest.TestCase):
    def test_every_shim_exposes_its_module(self):
        for file_name, module_name in support.SHIMS.items():
            with self.subTest(shim=file_name):
                shim = support.load_file(support.TOOLS_ROOT / file_name, "shim_under_test_" + module_name)
                module = support.package_module(module_name)
                self.assertIs(shim._implementation, module)
                names = {k for k in vars(module) if not k.startswith("__")}
                self.assertLessEqual(names, set(vars(shim)))
                for name in names:
                    self.assertIs(getattr(shim, name), getattr(module, name), name)
                if module_name != "registry":
                    self.assertTrue(callable(shim.main))


if __name__ == "__main__":
    unittest.main()
