# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""registry: C and Rust fixture registries; every policy switch in both states; the product terms."""
import copy
import json
import os
import unittest
from unittest import mock

import maint_support as support

registry = support.package_module("registry")


class RegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("registry")

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def c_product(self, name, shape="dcb", changes=None, extra_cells=None, prefix=None):
        root = self.work.folder(name)
        prefix = prefix or support.fixture_config(shape)["product"]["symbol_prefix"]
        support.c_cell(root, "engine", prefix)
        support.c_cell(root, "provider/serial", prefix)
        cells = {"engine": support.c_entry("engine", ("windows", "arm")),
                 "serial": support.c_entry("provider/serial", ("windows", "arm"),
                                           budget={"cortex-m4": {"text": 1, "data": 0, "bss": 0}})}
        cells.update(extra_cells or {})
        return root, support.product(root, shape, cells, changes=changes)

    def test_product_terms_follow_the_configuration(self):
        root, settings = self.c_product("terms")
        cells = registry.load_registry(settings)["cells"]
        serial = cells["serial"]
        self.assertEqual((serial.stem, serial.registration, serial.library_environment, serial.test_pattern),
                         ("dcb_provider_serial", "dcb_provider_serial_registration", "DCB_PROVIDER_SERIAL_LIBRARY",
                          "test_dcb_provider_serial_*.py"))
        self.assertEqual(serial.root, os.path.join(str(root), "10_pkg", "c", "provider", "serial"))
        self.assertEqual(cells["engine"].library_name, "dcb_engine.dll")
        self.assertEqual(registry.get_cell("engine", settings).public_header, "membrane/xpt_dcb_engine.h")

    def test_target_names(self):
        _root, settings = self.c_product("targets_arm")
        self.assertEqual(sorted(registry.load_registry(settings)["cells"]["engine"].targets), ["arm", "windows"])
        root = self.work.folder("targets_windows")
        support.c_cell(root, "engine", "wsb")
        settings = support.product(root, "wsb", {"engine": support.c_entry("engine", ("windows", "arm"))}, cores={})
        with self.assertRaisesRegex(registry.RegistryError, "only windows"):
            registry.load_registry(settings)

    def test_provider_budget_policy(self):
        root = self.work.folder("budget")
        support.c_cell(root, "provider/serial", "dcb")
        cells = {"serial": support.c_entry("provider/serial", ("windows",))}
        settings = support.product(root, "dcb", cells)
        with self.assertRaisesRegex(registry.RegistryError, "declares its cross-build budget"):
            registry.load_registry(settings)
        settings = support.product(root, "dcb", cells, changes={"provider_budget_required": "cross_build_only"})
        self.assertIsNone(registry.load_registry(settings)["cells"]["serial"].budget)
        cells = {"serial": support.c_entry("provider/serial", ("windows", "arm"))}
        settings = support.product(root, "dcb", cells, changes={"provider_budget_required": "cross_build_only"})
        with self.assertRaisesRegex(registry.RegistryError, "cross-built Provider declares its budget"):
            registry.load_registry(settings)

    def test_membrane_header_exclusions(self):
        root = self.work.folder("exclusions")
        support.c_cell(root, "engine", "dcb")
        support.write(root / "10_pkg" / "c" / "engine" / "membrane" / "xpt_dcb_engine_types.h", "/* types */\n")
        cells = {"engine": support.c_entry("engine")}
        with self.assertRaisesRegex(registry.RegistryError, "exactly one xpt"):
            registry.load_registry(support.product(root, "dcb", cells))
        settings = support.product(root, "dcb", cells, changes={"membrane_header_exclusions": ["_types.h"]})
        self.assertEqual(registry.load_registry(settings)["cells"]["engine"].public_header, "membrane/xpt_dcb_engine.h")

    def owned_library(self, links_binding):
        root = self.work.folder("owned_%s" % links_binding)
        for path in ("abi", "host", "platform/windows"):
            support.c_cell(root, path, "dcb", header=path != "platform/windows")
        cells = {"host": support.c_entry("host"),
                 "windows": support.c_entry("platform/windows", freestanding=False, depends_on=["host"], exports=["host"]),
                 "abi": support.c_entry("abi", library_from="windows", exports=["abi", "host"])}
        return support.product(root, "dcb", cells, changes={"owned_library_links_binding": links_binding})

    def test_owned_library_links_binding(self):
        with self.assertRaisesRegex(registry.RegistryError, "exports host, which its library does not link"):
            registry.load_registry(self.owned_library(False))
        abi = registry.load_registry(self.owned_library(True))["cells"]["abi"]
        self.assertEqual([cell.name for cell in abi.exported_cells()], ["abi", "host"])
        self.assertEqual([cell.name for cell in abi.library_plan()[1]], ["host", "windows"])

    def test_passive_include_roots_and_fixture_units(self):
        root = self.work.folder("passive")
        support.c_cell(root, "engine", "wsb", sources=("smo_%s.c", "efx_%s.c"))
        support.write(root / "10_pkg" / "binding" / "include" / "x.h", "/* passive */\n")
        support.write(root / "10_pkg" / "test" / "c" / "engine" / "fixture" / "f.c", "int f;\n")
        entry = support.c_entry("engine", passive_include_roots=["10_pkg/binding/include"], test_fixture="fixture",
                                fixture_units=["core/smo_wsb_engine.c"])
        cell = registry.load_registry(support.product(root, "wsb", {"engine": entry}, cores={}))["cells"]["engine"]
        self.assertEqual(cell.passive_include_roots(), [os.path.join(str(root), "10_pkg", "binding", "include")])
        self.assertEqual(cell.fixture_units, ["core/smo_wsb_engine.c"])
        self.assertEqual(cell.fixture_library_name, "wsb_engine_fixture.dll")
        for change, pattern in (({"passive_include_roots": ["10_pkg/absent"]}, "repository folder"),
                                ({"fixture_units": ["core/absent.c"]}, "fixture_units"),
                                ({"fixture_units": ["core/smo_wsb_engine.c"], "link_fixture": True}, "fixture_units")):
            bad = dict(copy.deepcopy(entry), **change)
            with self.subTest(change=change), self.assertRaisesRegex(registry.RegistryError, pattern):
                registry.load_registry(support.product(root, "wsb", {"engine": bad}, cores={}))

    def test_sdk_dependencies(self):
        root = self.work.folder("sdk")
        support.c_cell(root, "provider/cstat", "wsb")
        support.c_cell(root, "engine", "wsb")
        cells = {"cstat": support.c_entry("provider/cstat", sdk_dependencies=["wsb_shell"]),
                 "engine": support.c_entry("engine")}
        settings = support.product(root, "sunset", cells, cores={})
        cell = registry.load_registry(settings)["cells"]["cstat"]
        self.assertEqual(cell.sdk_dependencies, ["wsb_shell"])
        sdk = self.work.folder("sdk_root")
        with mock.patch.dict(os.environ, {"WSB_SDK_ROOT": str(sdk)}):
            with self.assertRaisesRegex(registry.RegistryError, "family vocabulary"):
                cell.standard_roots()
            support.write(sdk / "include" / "wsb_provider.h", "/* family */\n")
            support.write(sdk / "include" / "shell" / "membrane" / "xpt_wsb_shell.h", "/* shell */\n")
            self.assertEqual(cell.standard_roots(), [str((sdk / "include").resolve()),
                                                     str((sdk / "include" / "shell" / "membrane").resolve())])
        with mock.patch.dict(os.environ, {"WSB_SDK_ROOT": ""}):
            with self.assertRaisesRegex(registry.RegistryError, "absolute SDK"):
                cell.standard_roots()
        bad = dict(cells, cstat=support.c_entry("provider/cstat"))
        with self.assertRaisesRegex(registry.RegistryError, "SDK dependencies"):
            registry.load_registry(support.product(root, "sunset", bad, cores={}))
        with self.assertRaisesRegex(registry.RegistryError, "may hold"):
            registry.load_registry(support.product(root, "wsb", cells, cores={}))

    def test_external_header_environment_uses_the_product_prefix(self):
        root = self.work.folder("external")
        support.c_cell(root, "freertos", "dcb")
        support.write(root / "10_pkg" / "test" / "config" / "x.h", "/* config */\n")
        section = {"environment": "WSB_KERNEL", "commit": "0" * 40, "include_roots": ["include"],
                   "core_include_roots": {"cortex-m4": []}, "gate_core": "cortex-m4", "config_roots": ["10_pkg/test/config"]}
        cells = {"freertos": support.c_entry("platform/freertos".split("/")[-1], ("arm",), external_headers=section)}
        with self.assertRaisesRegex(registry.RegistryError, "DCB_\\* variable"):
            registry.load_registry(support.product(root, "dcb", cells))
        section["environment"] = "DCB_KERNEL"
        cell = registry.load_registry(support.product(root, "dcb", cells))["cells"]["freertos"]
        with mock.patch.dict(os.environ, {"DCB_KERNEL": ""}):
            with self.assertRaisesRegex(registry.RegistryError, "DCB_KERNEL"):
                cell.external_roots("cortex-m4")

    def test_stems_symbols_and_cycles(self):
        with self.assertRaisesRegex(registry.RegistryError, "2 .c files"):
            registry.require_unique_stems([("a", "core/smo_x.c", None), ("b", "core/smo_x.c", None)])
        self.assertEqual(registry.require_unique_stems([("a", "contract/pvo_x.h", "G"), ("b", "contract/pvo_x.h", "G")]), 1)
        with self.assertRaisesRegex(registry.RegistryError, "more than once"):
            registry.require_unique_symbols({"a/x.c": ["f"], "b/y.c": ["f"]})
        self.assertEqual(registry.external_symbols("0000 T f\n0000 U g\n0000 t h\n0000 D v\n"), ["f", "v"])
        self.assertEqual(registry.object_name("x.c"), "o_%s.o" % __import__("hashlib").sha256(b"x.c").hexdigest()[:16])
        root, _settings = self.c_product("cycle")
        support.c_cell(root, "driver", "dcb")
        cells = {"engine": support.c_entry("engine", depends_on=["driver"]),
                 "driver": support.c_entry("driver", depends_on=["engine"])}
        with self.assertRaisesRegex(registry.RegistryError, "cycle"):
            registry.load_registry(support.product(root, "dcb", cells))

    def test_rust_registry(self):
        root = self.work.folder("rust")
        crate = root / "10_pkg" / "rust" / "provider" / "sim"
        support.write(crate / "Cargo.toml", "[package]\n")
        support.write(crate / "cell" / "comsect1.json", "{}\n")
        for zone in ("contract", "core", "capability", "membrane"):
            support.write(crate / "cell" / zone / "mod.rs", "// zone\n")
        settings = support.product(root, "hsb", {"sim": {"path": "provider/sim", "edition": "2021", "depends_on": []}})
        cell = registry.load_registry(settings)["cells"]["sim"]
        self.assertIsInstance(cell, registry.RustCell)
        self.assertEqual((cell.stem, cell.library_environment), ("hsb_provider_sim", "HSB_PROVIDER_SIM_LIBRARY"))
        self.assertEqual(len(cell.sources), 4)
        settings = support.product(root, "hsb", {"sim": {"path": "provider/sim", "edition": "21", "depends_on": []}})
        with self.assertRaisesRegex(registry.RegistryError, "edition"):
            registry.load_registry(settings)


if __name__ == "__main__":
    unittest.main()
