# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Explicit native analysis toolchain admission (moved from WSB); fixtures removed through 99_trash."""
from contextlib import ExitStack
import hashlib
import json
import os
import unittest

import maint_support as support

tool = support.package_module("native_gate")


@unittest.skipUnless(os.name == "nt", "toolchain admission locks inputs with Windows handles")
class NativeToolchainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("native_toolchain")

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def setUp(self):
        self.root = self.work.folder(self._testMethodName)
        values = {"bin/clang.exe": b"fixture compiler", "bin/libclang.dll": b"fixture runtime",
                  "lib/clang/19/include/stdint.h": b"fixture uint", "lib/clang/19/include/stddef.h": b"fixture size"}
        self.runtime = hashlib.sha256(values["bin/libclang.dll"]).hexdigest()
        rows = []
        for relative, data in values.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            rows.append({"path": relative, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.record = {"kind": "native_c_toolchain_inputs",
                       "source": {"release_url": "https://example.invalid/release", "release_tag": "test",
                                  "archive_url": "https://example.invalid/archive", "archive_name": "test.tar.xz",
                                  "archive_size": 1, "archive_sha256": "a" * 64},
                       "compiler": "bin/clang.exe", "semantic_runtime": "bin/libclang.dll",
                       "resource_directory": "lib/clang/19", "files": rows}
        self.pin()

    def pin(self):
        data = json.dumps(self.record).encode()
        (self.root / "provenance.json").write_bytes(data)
        self.config = {"clang_resource": {"manifest": str(self.root / "provenance.json"),
                                         "manifest_sha256": hashlib.sha256(data).hexdigest()}}

    def admit(self, runtime=None):
        with ExitStack() as locks:
            return tool.find_clang(self.config, runtime or self.runtime, locks)

    def test_exact_inventory_and_runtime_admit_without_path_discovery(self):
        compiler, resource = self.admit()
        self.assertEqual(compiler, self.root / "bin/clang.exe")
        self.assertEqual(resource, self.root / "lib/clang/19/include")
        self.assertEqual(self.config["_native_toolchain"]["member_count"], 4)
        self.assertEqual(self.config["_native_toolchain"]["members_differ"], [])

    def test_changed_manifest_digest_is_recorded_not_refused(self):
        with (self.root / "provenance.json").open("ab") as stream: stream.write(b" ")
        self.admit()
        record = self.config["_native_toolchain"]
        self.assertNotEqual(record["manifest_sha256"], record["manifest_sha256_recorded"])

    def test_other_semantic_runtime_is_recorded_not_refused(self):
        self.admit("0" * 64)
        record = self.config["_native_toolchain"]
        self.assertEqual(record["semantic_runtime_sha256"], "0" * 64)
        self.assertEqual(record["semantic_runtime_sha256_listed"], self.runtime)

    def test_changed_resource_same_size_is_recorded_not_refused(self):
        (self.root / "lib/clang/19/include/stdint.h").write_bytes(b"fixture sint")
        self.admit()
        self.assertEqual(self.config["_native_toolchain"]["members_differ"], ["lib/clang/19/include/stdint.h"])

    def test_unlisted_header_is_refused(self):
        (self.root / "lib/clang/19/include/extra.h").write_bytes(b"unapproved")
        with self.assertRaisesRegex(tool.ToolError, "complete inventory"): self.admit()

    def test_traversal_and_case_alias_are_refused(self):
        self.record["files"][0]["path"] = "../outside"
        self.pin()
        with self.assertRaisesRegex(tool.ToolError, "unsafe"): self.admit()
        self.record["files"][0]["path"] = "BIN/libclang.dll"
        self.pin()
        with self.assertRaisesRegex(tool.ToolError, "duplicate"): self.admit()

    def test_missing_explicit_manifest_never_discovers_android(self):
        self.config["clang_resource"]["manifest"] = str(self.root / "missing.json")
        with self.assertRaisesRegex(tool.ToolError, "unavailable"): self.admit()

    def test_admitted_bytes_cannot_be_rewritten_while_in_use(self):
        path = self.root / "lib/clang/19/include/stdint.h"
        with ExitStack() as locks:
            tool.find_clang(self.config, self.runtime, locks)
            with self.assertRaises(PermissionError): path.write_bytes(b"changed")
        path.write_bytes(b"released")

if __name__ == "__main__": unittest.main()
