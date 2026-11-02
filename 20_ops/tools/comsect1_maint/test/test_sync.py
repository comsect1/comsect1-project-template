# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""sync: manifest write and check round trip; modified, missing and extra common files are reported."""
import json
import shutil
import unittest

import maint_support as support

sync = support.package_module("sync")


class SyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("sync")

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def copy_tools(self, name):
        tools = self.work.folder(name) / "20_ops" / "tools"
        shutil.copytree(support.PACKAGE_ROOT, tools / "comsect1_maint", ignore=shutil.ignore_patterns("__pycache__"))
        for file_name in sync.SHIMS + sync.ROOT_FILES:
            shutil.copyfile(support.TOOLS_ROOT / file_name, tools / file_name)
        return tools

    def test_this_checkout_matches_its_manifest(self):
        language = sync.product_language(str(support.TOOLS_ROOT))
        self.assertEqual(sync.check(str(support.TOOLS_ROOT), language), [])

    def test_round_trip_and_findings(self):
        tools = self.copy_tools("round_trip")
        sync.write_manifest(str(tools))
        self.assertEqual(sync.check(str(tools)), [])
        support.write(tools / "comsect1_maint" / "registry.py", "# local edit\n")
        (tools / "gate.py").unlink()
        support.write(tools / "comsect1_maint" / "extra.py", "# stray\n")
        self.assertEqual(sync.check(str(tools)), [("EXTRA", "comsect1_maint/extra.py"),
                                                  ("MODIFIED", "comsect1_maint/registry.py"), ("MISSING", "gate.py")])

    def test_a_rust_product_needs_only_the_registry_shim(self):
        tools = self.copy_tools("rust")
        sync.write_manifest(str(tools))
        for name in ("build.py", "gate.py", "native_gate.py", "cross_build.py"):
            (tools / name).unlink()
        support.write(tools / "maint_config.json", json.dumps({"language": "rust"}))
        self.assertEqual(sync.check(str(tools), sync.product_language(str(tools))), [])
        self.assertEqual(len(sync.check(str(tools), "c")), 4)

    def test_manifest_shape_is_checked(self):
        tools = self.copy_tools("shape")
        support.write(tools / "comsect1_maint" / "sync_manifest.json", json.dumps({"schema": "other", "files": {}}))
        with self.assertRaisesRegex(sync.SyncError, "not a"):
            sync.check(str(tools))


if __name__ == "__main__":
    unittest.main()
