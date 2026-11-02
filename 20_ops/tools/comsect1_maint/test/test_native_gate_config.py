# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""native_gate.load_config: both clang_resource shapes, a mixed one refused, publications optional."""
import json
import unittest

import maint_support as support

driver = support.package_module("native_gate")
BASE = json.loads((support.FIXTURES / "native_gate_config.json").read_text(encoding="utf-8"))
MANIFEST = {"manifest": "%LOCALAPPDATA%/toolchain/provenance.json", "manifest_sha256": "a" * 64}


class LaneConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("native_gate_config")

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def load(self, value, name):
        path = support.write(self.work.path / (name + ".json"), json.dumps(value, indent=2) + "\n")
        return driver.load_config(path)

    def test_discovery_shape(self):
        config = self.load(BASE, "discovery")
        self.assertEqual(config["_clang_mode"], "discovery")
        self.assertEqual(config["publications"], [])

    def test_manifest_shape_with_publications(self):
        value = dict(BASE, clang_resource=MANIFEST, publications=[
            {"canonical_root": "%WSB_SDK_ROOT%", "inventory_member": "wsb-sdk.swidtag",
             "declaration_member": "binding/native_publication.json"}])
        config = self.load(value, "manifest")
        self.assertEqual(config["_clang_mode"], "manifest")
        self.assertEqual(len(config["publications"]), 1)

    def test_mixed_or_partial_clang_shape_is_refused(self):
        for name, clang in (("mixed", dict(BASE["clang_resource"], **MANIFEST)),
                            ("partial", {"manifest": MANIFEST["manifest"]}),
                            ("empty", {})):
            with self.subTest(shape=name), self.assertRaises(driver.ToolError) as caught:
                self.load(dict(BASE, clang_resource=clang), name)
            self.assertEqual(caught.exception.code, driver.EXIT_CONFIG)
            self.assertIn("pinned manifest", caught.exception.message)

    def test_bad_manifest_digest_and_publication_member_are_refused(self):
        with self.assertRaisesRegex(driver.ToolError, "pin the provenance"):
            self.load(dict(BASE, clang_resource=dict(MANIFEST, manifest_sha256="A" * 64)), "digest")
        with self.assertRaisesRegex(driver.ToolError, "unaliased"):
            self.load(dict(BASE, publications=[{"canonical_root": "C:/sdk", "inventory_member": "../x",
                                                "declaration_member": "d.json"}]), "publication")

    def test_unknown_member_is_refused(self):
        with self.assertRaisesRegex(driver.ToolError, "exactly the members"):
            self.load(dict(BASE, extra=True), "extra")


if __name__ == "__main__":
    unittest.main()
