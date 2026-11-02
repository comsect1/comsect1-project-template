# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""config: the four product shapes load; one refusal per rule; hooks and the template origin."""
import copy
import json
import unittest

import maint_support as support

config = support.config


class ConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("config")

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def refused(self, raw, pattern):
        with self.assertRaisesRegex(config.ConfigError, pattern):
            config.validate(raw)

    def test_every_product_shape_loads(self):
        for name in ("dcb", "hsb", "wsb", "sunset"):
            with self.subTest(product=name):
                root = self.work.folder("shape_" + name)
                path = support.write(root / "20_ops" / "tools" / "maint_config.json",
                                     json.dumps(support.fixture_config(name)))
                settings = config.load(str(path))
                self.assertEqual(settings.product_id, name)
                self.assertEqual(settings.repo_root, str(root))

    def test_unknown_key_absolute_path_and_language_keys_are_refused(self):
        raw = support.fixture_config("dcb")
        self.refused(dict(raw, extra=1), "exactly")
        bad = copy.deepcopy(raw)
        bad["registry"]["path"] = "C:/repo/cells.json"
        self.refused(bad, "repository-relative")
        bad = copy.deepcopy(raw)
        bad["native_gate"]["config"] = "20_ops/../x.json"
        self.refused(bad, "repository-relative")
        bad = copy.deepcopy(raw)
        bad["language"] = "rust"
        self.refused(bad, "rust")
        rust = support.fixture_config("hsb")
        rust["registry"]["target_names"] = ["windows"]
        self.refused(rust, "exactly")
        bad = copy.deepcopy(raw)
        bad["host_build"]["compiler_bin_dir"] = "msys64/bin"
        self.refused(bad, "absolute")

    def test_value_rules(self):
        raw = support.fixture_config("dcb")
        for section, key, value, pattern in (
                ("product", "symbol_prefix", "DCB", "symbol_prefix"),
                ("product", "environment_prefix", "dcb", "environment_prefix"),
                ("registry", "target_names", ["windows", "riscv"], "windows and arm"),
                ("registry", "provider_budget_required", "never", "provider_budget_required"),
                ("registry", "membrane_header_exclusions", ["types.h"], "membrane_header_exclusions"),
                ("host_build", "provider_family", {"kind": "negotiate_offers", "offers": [["port", 1, 1], ["port", 2, 1]]},
                 "distinct"),
                ("host_build", "provider_export_aliases", ["bad-name"], "provider_export_aliases")):
            bad = copy.deepcopy(raw)
            bad[section][key] = value
            with self.subTest(key=key):
                self.refused(bad, pattern)
        self.refused(dict(copy.deepcopy(raw), schema="comsect1.maint_config"), "schema")

    def test_a_required_hook_needs_a_module_and_the_function(self):
        raw = support.fixture_config("wsb")
        self.refused(dict(copy.deepcopy(raw), hooks=None), "hook")
        root = self.work.folder("hooks")
        path = support.write(root / "20_ops" / "tools" / "maint_config.json", json.dumps(raw))
        settings = config.load(str(path))
        with self.assertRaisesRegex(config.ConfigError, "not a regular file"):
            settings.hook("provider_family")
        support.write(root / "20_ops" / "tools" / "product_hooks.py",
                      "def build_evidence(cell, run_dir, record):\n    return record\n")
        settings = config.load(str(path))
        self.assertTrue(callable(settings.hook("build_evidence")))
        self.assertIsNone(settings.hook("gate_publications", required=False))
        with self.assertRaisesRegex(config.ConfigError, "no required hook provider_family"):
            settings.hook("provider_family")
        with self.assertRaisesRegex(config.ConfigError, "unknown hook"):
            settings.hook("anything")
        dcb = config.load(str(support.write(self.work.folder("nohooks") / "20_ops" / "tools" / "maint_config.json",
                                            json.dumps(support.fixture_config("dcb")))))
        self.assertIsNone(dcb.hook("build_evidence", required=False))
        with self.assertRaisesRegex(config.ConfigError, "names no hook module"):
            dcb.hook("provider_family")

    def test_template_origin_is_required_for_a_product_run(self):
        root = self.work.folder("origin")
        with self.assertRaisesRegex(config.DriftError, "unreadable"):
            config.origin(str(root))
        support.write(root / ".instructions" / "template-origin.json",
                      json.dumps({"schema": "comsect1.template-origin.v1", "template": "comsect1-project-template",
                                  "baseline_commit": "27b7c727920c230427a27ba6b81b3758f5ac3b79"}))
        self.assertEqual(config.origin(str(root))["template"], "comsect1-project-template")
        with self.assertRaisesRegex(config.DriftError, "drift"):
            config.maintainer_tools(str(root), False, "c")
        member = config.maintainer_tools(str(root), True, "c")
        self.assertTrue(member["tool_drift_accepted"])
        self.assertEqual(member["baseline_commit"], "27b7c727920c230427a27ba6b81b3758f5ac3b79")


if __name__ == "__main__":
    unittest.main()
