# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Driver owner selection (moved from WSB); actual native capture is verified separately."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import maint_support as support

driver = support.package_module("native_gate")


class InputOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = support.Run("native_input_owners")
        cls.run_root = cls.work.path

    @classmethod
    def tearDownClass(cls):
        cls.work.close()

    def setUp(self):
        self.root = self.run_root / self._testMethodName
        self.root.mkdir()
        self.cell = self.root / 'target'
        self.cell.mkdir()
        (self.cell / 'comsect1.json').write_bytes(b'{}\n')
        self.config = json.loads((support.FIXTURES / 'native_gate_config.json').read_bytes())

    def file(self, relative, data=b'/* selected input */\n'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def source(self):
        self.file('dependency/comsect1.json', b'{}\n')
        return self.file('dependency/membrane/xpt_dependency.h')

    def publication(self):
        header = self.file('sdk/include/entry.h')
        row = {'canonical_root': (self.root / 'sdk').as_posix(),
               'inventory_member': 'sdk.swidtag',
               'declaration_member': 'binding/native_publication.json'}
        self.config['publications'] = [row]
        return header, row

    def select(self, inputs):
        return driver.input_owner_selection(self.config, inputs, self.cell)

    def test_source_and_library_inputs_keep_distinct_origins(self):
        source = self.source()
        library = self.file('library/header.h')
        roots, publications = self.select({'source': str(source), 'library': str(library)})
        self.assertEqual(roots, [self.root / 'dependency'])
        self.assertEqual(publications, [])

    def test_narrowed_include_directory_does_not_hide_original_control(self):
        source = self.source()
        roots, _ = self.select({'entry': str(source)})
        self.assertEqual(roots, [source.parent.parent])

    def test_nested_original_controls_are_refused(self):
        source = self.source()
        self.file('dependency/membrane/comsect1.json', b'{}\n')
        with self.assertRaisesRegex(driver.ToolError, 'nested original'):
            self.select({'entry': str(source)})

    def test_governed_file_cannot_be_external(self):
        source = self.file('target/owned.h')
        with self.assertRaisesRegex(driver.ToolError, 'governed Cell'):
            self.select({'wrong': str(source)})

    def test_publication_selection_is_exact_and_unused_owner_is_omitted(self):
        header, row = self.publication()
        roots, selected = self.select({'sdk_entry': str(header)})
        self.assertEqual(roots, [])
        self.assertEqual(selected, [row])
        library = self.file('library/header.h')
        self.assertEqual(self.select({'library': str(library)}), ([], []))

    def test_overlapping_publication_roots_are_refused(self):
        header, row = self.publication()
        self.config['publications'].append(dict(row, canonical_root=str(header.parent)))
        with self.assertRaisesRegex(driver.ToolError, 'overlapping publication'):
            self.select({'sdk_entry': str(header)})

    def test_linked_control_is_refused_before_capture(self):
        source = self.source()
        original = driver.is_link
        control = source.parent.parent / 'comsect1.json'
        with patch.object(driver, 'is_link', side_effect=lambda path: Path(path) == control or original(path)):
            with self.assertRaisesRegex(driver.ToolError, 'invalid original Cell control'):
                self.select({'entry': str(source)})

    def test_configuration_requires_exact_publication_shape(self):
        header, row = self.publication()
        path = self.root / 'config.json'
        cases = [None, [dict(row, root=row['canonical_root'])],
                 [dict(row, declaration_member='../escape.json')]]
        for value in cases:
            with self.subTest(value=value):
                self.config['publications'] = value
                path.write_text(json.dumps(self.config) + '\n', encoding='utf-8', newline='\n')
                with self.assertRaises(driver.ToolError):
                    driver.load_config(path)

    def test_driver_passes_exact_selections_to_owner_cli(self):
        source = self.source()
        header, row = self.publication()
        inputs = {'source_entry': str(source), 'sdk_entry': str(header)}
        item = {'configuration_id': 'translation', 'publication_authority_id': None}
        commands = []
        def process(name, command, *args):
            commands.append([str(arg) for arg in command])
            return (0, 'sha256:' + 'a' * 64 + '\n', '') if name.startswith('native-input') else (0, '', '')
        with patch.object(driver, 'include_directories', return_value=[]), \
             patch.object(driver, 'configuration_for', return_value=(item, inputs)), \
             patch.object(driver, 'run_process', side_effect=process), \
             patch.object(driver, 'read_report', return_value={'verdict': 'PASS'}):
            driver.run_native_lane(self.config, {'native_input': 'owner-input', 'gate': 'owner-gate'},
                                   self.cell, ['fixture.c'], 'clang', 'resource', self.root / 'lane')
        command = commands[0]
        self.assertEqual(command[command.index('--source-cell') + 1], str(source.parent.parent))
        descriptor = Path(command[command.index('--publication') + 1])
        self.assertEqual(json.loads(descriptor.read_bytes()), row)
        self.assertIn('source_entry=' + str(source), command)
        self.assertIn('sdk_entry=' + str(header), command)
        self.assertEqual(item['publication_authority_id'], 'sha256:' + 'a' * 64)

    def test_dotdot_checks_the_cancelled_component(self):
        membrane = self.root / 'sdk' / 'membrane'
        membrane.mkdir(parents=True)
        contract = self.file('sdk/contract/header.h')
        raw = membrane / '..' / 'contract' / 'header.h'
        self.assertEqual(driver.checked_original_path(raw), contract)
        original = driver._path_guard.os.path.isjunction
        with patch.object(driver._path_guard.os.path, 'isjunction',
                          side_effect=lambda p: Path(p) == membrane or original(p)):
            with self.assertRaisesRegex(driver.ToolError, 'reparse'):
                driver.checked_original_path(raw)

    def test_file_cannot_be_cancelled_by_dotdot(self):
        leaf = self.file('sdk/file')
        self.file('sdk/header.h')
        with self.assertRaisesRegex(driver.ToolError, 'non-directory'):
            driver.checked_original_path(leaf / '..' / 'header.h')

    def test_anchor_is_checked(self):
        header = self.file('sdk/header.h')
        anchor = Path(header.anchor)
        original = driver._path_guard.os.path.isjunction
        with patch.object(driver._path_guard.os.path, 'isjunction',
                          side_effect=lambda p: Path(p) == anchor or original(p)):
            with self.assertRaisesRegex(driver.ToolError, 'reparse'):
                driver.checked_original_path(header)

    @unittest.skipUnless(driver._path_guard.os.name == 'nt', 'Windows path semantics')
    def test_ambiguous_windows_paths_are_refused(self):
        for raw in (self.root.drive + 'relative.h', '\\relative.h'):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(driver.ToolError, 'ambiguous'):
                    driver.checked_original_path(raw)

    def test_include_and_system_root_reparse_refused(self):
        include = self.cell / 'include'
        include.mkdir()
        self.config['build']['include_roots'] = ['include']
        self.config['build']['external_include_roots'] = []
        self.config['build']['system_include_roots'] = [str(include)]
        original = driver._path_guard.os.path.isjunction
        with patch.object(driver._path_guard.os.path, 'isjunction',
                          side_effect=lambda p: Path(p) == include or original(p)):
            with self.assertRaisesRegex(driver.ToolError, 'reparse'):
                driver.include_directories(self.config, self.cell)
            with self.assertRaisesRegex(driver.ToolError, 'reparse'):
                driver.system_directories(self.config)

    def test_clang_original_dependency_and_cell_ancestor_are_checked(self):
        parent = self.root / 'alias'
        parent.mkdir()
        cell = parent / 'cell'
        cell.mkdir()
        (cell / 'comsect1.json').write_bytes(b'{}')
        (cell / 'unit.c').write_bytes(b'/* fixture */')
        original = driver._path_guard.os.path.isjunction
        with patch.object(driver._path_guard.os.path, 'isjunction',
                          side_effect=lambda p: Path(p) == parent or original(p)):
            with self.assertRaisesRegex(driver.ToolError, 'reparse'):
                driver.check_cell(cell)
            with patch.object(driver, 'run_process', return_value=(0, 'out: ' + str(cell / 'unit.c'), '')):
                with self.assertRaisesRegex(driver.ToolError, 'reparse'):
                    driver.header_closure(self.config, 'clang', 'resource', [], cell / 'unit.c', self.root)


if __name__ == '__main__':
    unittest.main()
