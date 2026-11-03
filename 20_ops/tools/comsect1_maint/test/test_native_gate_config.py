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
        self.assertNotIn("publications", config)

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
            self.assertIn("(manifest)", caught.exception.message)

    def test_bad_manifest_digest_and_publication_member_are_refused(self):
        with self.assertRaisesRegex(driver.ToolError, "record the provenance digest"):
            self.load(dict(BASE, clang_resource=dict(MANIFEST, manifest_sha256="A" * 64)), "digest")
        with self.assertRaisesRegex(driver.ToolError, "unaliased"):
            self.load(dict(BASE, publications=[{"canonical_root": "C:/sdk", "inventory_member": "../x",
                                                "declaration_member": "d.json"}]), "publication")

    def test_tool_hash_difference_is_recorded_not_refused(self):
        binary = support.write(self.work.path / "tool_binary.exe", "fixture tool\n")
        config = self.load(BASE, "tool_hash")
        paths = {key: binary for key in driver.TOOL_KEYS}
        actual, differs = driver.tool_hashes(config, paths)
        self.assertEqual(set(actual), set(driver.TOOL_KEYS))
        self.assertEqual(differs, [key for key in driver.TOOL_KEYS if config["expected_sha256"][key] != actual[key]])
        self.assertTrue(differs)

    def test_missing_gate_set_names_the_path_and_the_next_step(self):
        root = self.work.path / "gate_runtime"
        config = self.load(dict(BASE, gate_set=dict(BASE["gate_set"], runtime_root=str(root))), "gate_set")
        with self.assertRaises(driver.ToolError) as caught:
            driver.resolve_gate_set(config)
        self.assertIn(str(root / "current.json"), caught.exception.message)
        self.assertIn("Next step", caught.exception.message)
        support.write(root / "current.json", json.dumps({"set_path": "sets/a", "release_set_id": "set-a"}))
        (root / "sets" / "a" / "payload" / "bin").mkdir(parents=True)
        with self.assertRaises(driver.ToolError) as caught:
            driver.resolve_gate_set(config)
        self.assertEqual(caught.exception.code, driver.EXIT_TOOL_SET_UNAVAILABLE)
        for text in ("comsect1-gate.exe", "release set set-a", "Next step"):
            self.assertIn(text, caught.exception.message)

    def test_analysis_standard_follows_the_frontend(self):
        self.assertEqual(driver.analysis_standard(self.load(BASE, "c23")), "c23")
        c11 = dict(BASE, build=dict(BASE["build"], standard="c11"))
        self.assertEqual(driver.analysis_standard(self.load(c11, "c11")), "c11")
        older = dict(BASE, gate_set=dict(BASE["gate_set"], frontend_standards=["c99", "c11", "c17"]))
        self.assertEqual(driver.analysis_standard(self.load(older, "older")), "c17")
        newer = dict(c11, gate_set=dict(BASE["gate_set"], frontend_standards=["c17", "c23"]))
        with self.assertRaisesRegex(driver.ToolError, "none of them at or below"):
            self.load(newer, "newer")
        for name, value in (("empty", []), ("unknown", ["c89"]), ("twice", ["c17", "c17"])):
            with self.subTest(frontend=name), self.assertRaisesRegex(driver.ToolError, "frontend_standards"):
                self.load(dict(BASE, gate_set=dict(BASE["gate_set"], frontend_standards=value)), name)

    def test_unknown_member_is_refused(self):
        with self.assertRaisesRegex(driver.ToolError, "exactly the members"):
            self.load(dict(BASE, extra=True), "extra")


if __name__ == "__main__":
    unittest.main()
