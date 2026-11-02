# Shared maintainer tools design directive

Date: 2026-11-02. Work revision r1 (design only; nothing implemented).

Authority: `fnd-architecture` reference model section 8, finding T2
("`native_gate.py`, `native_path_guard.py`, `cross_build.py`,
`cell_registry.py` and `build.py` are copied between DCB, HSB, WSB and
Sunset"); recommendation already recorded there: move the shared maintainer
tools into the project template and keep product configuration local.

Scope: maintainer-only tools under `20_ops/tools/`. The SDK-user tool
`tools/comsect1_sdk.pyz` (Foundation `fnd-sdk-standard`, distribution 8.5,
finding T1) is SDK content and stays out of this design; see section 9.

## 1. Evidence: what is copied today

Inventory of 2026-11-02 (`python -I -B` AST comparison per top-level
function, class and module constant; line counts are physical lines).

| File | DCB | HSB | WSB | Sunset | Finding |
|---|---|---|---|---|---|
| `native_gate.py` | 707 | absent | 883 | 883 | WSB and Sunset byte-identical. DCB is the 2026-10-24 origin; WSB/Sunset forked it on 2026-10-28 with toolchain-manifest admission, path guard, publications and input-owner selection (9 added units, `find_clang` rewritten). DCB alone kept `check_resource`/`clang_candidates` discovery and alone validates `outcome_summary` in `read_report`. 56 units identical, 10 differ, 1 DCB-only. |
| `native_path_guard.py` | absent | absent | 30 | 30 | Identical. Pure common code, no product term. |
| `cross_build.py` | 272 | absent | 272 | 272 | DCB and Sunset byte-identical. WSB differs in one line of `build` (adds `passive_include_roots()`). 20 units identical. |
| `cell_registry.py` | 603 | 131 | 627 | 627 | C registry (DCB/WSB/Sunset): 26 units identical, 8 differ. Differences are product terms (`dcb_`/`wsb_` stems, `DCB_*`/`WSB_*` environment pattern, `TARGET_NAMES` with or without `arm`), policy switches (Provider budget always vs only when cross-built; `library_plan` linking; `xpt_*_types.h` exclusion) and two product extensions (WSB `fixture_units` + hard-coded `passive_include_roots` table; Sunset `sdk_dependencies` + `WSB_SDK_ROOT` roots). HSB is a Rust registry (`path`, `edition`, `depends_on`) sharing only the skeleton (name/path rules, `_require`, `_require_acyclic`, `get_cell`). |
| `build.py` | 818 | 671 | 844 | 783 | C host build (DCB/WSB/Sunset): 40 units identical, 12 differ, 19 single-product. Differences: product prefix in 5 places; `CREATE_NO_WINDOW` present in WSB only; gcc response files in DCB only; `_provider_family` has three implementations (DCB: ctypes negotiate over family offers; WSB: `wsb_hosted.registration_family`; Sunset: `wsb_policy.hosted` from the selected SDK archive); WSB `fixture_units`, `_source_dependencies`, `native_build_evidence`; Sunset `sdk_input_receipt` capture before/after and `libwsb_shell.a` link. HSB `build.py` is a cargo driver (`FreshBuildSession`, 391 lines) and is not a copy. |
| `gate.py` | 135 | 265 | 136 | 225 | DCB and WSB equal except the WSB passive-roots line. Sunset hardened `_is_link`, `quarantine` (inventory and inode check), `_checked_path`, `_check_tree` and derives Provider `publications` from `WSB_SDK_ROOT`. HSB is a different Rust Gate driver. |
| `text-format.ps1` | 106 | 106 | 106 | 111 | Already template-owned; Comsect1 template, DCB, HSB and WSB identical. Hatbit template carries a compacted copy; Sunset carries an improvement (`--cached --others --exclude-standard`, so untracked files are checked). |
| `package.py` | 1769 | 860 | 1905 | absent | Not a copy: DCB/WSB share 66 units but differ in 35 and each has 12-44 own units; HSB is separate. Out of T2 (section 10). |
| `wsb_evidence.py`, `wsb_project.py` | 953, 540 | 786, 510 | owner | absent | WSB *consumer* tools copied between the two WSB adopters (36 + 21 identical units). Out of T2; candidate for WSB SDK content (section 10). |

Duplicated helpers inside every file (each copy re-implements them):
`_load_sibling`, `new_run_id`, `RUN_ID_PATTERN`, `_is_link`, `quarantine`,
`run_process`/`_run` with `CREATE_NO_WINDOW`, `kill_tree`, `sha256_file`,
`write_json`, `REPO_ROOT` discovery.

Loading contract that every consumer relies on and that the design keeps:
product tools and tests load a tool by file path
(`importlib.util.spec_from_file_location(..., "20_ops/tools/<tool>.py")`)
and call its public functions; `build.py`, `cross_build.py`, `gate.py`,
`package.py`, `wsb_evidence.py` load `cell_registry.py` the same way. The
only private name reached from outside is `native_gate._path_guard` (WSB and
Sunset report tests patch it).

## 2. Direction

One Python package `comsect1_maint` under `20_ops/tools/` of this template is
the single owner of the shared maintainer tools. A product keeps:

- one configuration file `20_ops/tools/maint_config.json` (section 4),
- its `cells.json` and `native_gate_config.json` (already product data),
- an optional `20_ops/tools/product_hooks.py` for logic that is not data
  (section 5),
- its own product-only tools (`package.py`, `fuzz.py`, HSB `build.py` and
  `gate.py`, Sunset `sdk_input_receipt.py`, ...), which import the package.

The package and five thin entry files travel as a common layer of template
synchronization (section 6). Product-specific behaviour is selected by
configuration and hooks, never by editing the package in a product; a needed
change goes upstream to the template and comes back by synchronization.

## 3. Module set and location

```
20_ops/tools/
  comsect1_maint/              common layer (template-owned, synced verbatim)
    __init__.py                package marker; exposes `origin()` (section 7)
    sync_manifest.json         sha256 of every common file (section 6)
    path_guard.py              <- native_path_guard.py (30 lines, as is)
    process.py                 extracted helpers: REPO_ROOT discovery, run_id,
                               run_process/kill_tree/CREATE_NO_WINDOW,
                               is_link (Sunset variant), checked_path,
                               check_tree, quarantine (Sunset variant),
                               sha256_file/text, write_json/text, load_sibling
    config.py                  maint_config.json loader, schema check,
                               hook loader, template-origin reader
    registry.py                <- cell_registry.py; language "c" and "rust"
    native_gate.py             <- native_gate.py (merged, section 3.1)
    cross_build.py             <- cross_build.py
    host_build.py              <- build.py (C host build)
    gate.py                    <- gate.py (C Gate driver, Sunset hardening)
    test/                      template-owned unit tests and fixtures
      test_path_guard.py test_process.py test_config.py test_registry.py
      test_native_gate_config.py test_native_gate_report.py
      test_native_gate_toolchain.py test_native_input_owners.py
      test_cross_build.py test_host_build.py
      fixtures/ (registry files for both languages, config examples per
                 product shape, synthetic toolchain tree, Gate reports)
  native_gate.py               entry shim  (common layer)
  cell_registry.py             entry shim  (common layer)
  cross_build.py               entry shim  (common layer)
  build.py                     entry shim  (common layer; HSB keeps its own)
  gate.py                      entry shim  (common layer; HSB keeps its own)
  text-format.ps1              common layer (already)
  maint_config.json            local layer (product)
  cells.json                   local layer (product)
  native_gate_config.json      local layer (product)
  product_hooks.py             local layer (product, optional)
  <other product tools>        local layer (product)
```

Estimated size of the package (from the merged copies): `path_guard` 30,
`process` ~150, `config` ~130, `registry` ~740 (C ~700 + Rust ~40),
`native_gate` ~930, `cross_build` ~250, `host_build` ~900, `gate` ~230,
shims 5 x ~14, tests ~1,200 (moved from the products, see section 8).

Entry shim (identical text in every product, template-owned):

```python
"""Entry for `native_gate`; the implementation is `comsect1_maint.native_gate`."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comsect1_maint import native_gate as _implementation
globals().update({k: v for k, v in vars(_implementation).items() if not k.startswith("__")})
if __name__ == "__main__":
    sys.exit(_implementation.main(sys.argv[1:]))
```

`globals().update` (not `import *`) keeps underscore names such as
`_path_guard` reachable, so `spec_from_file_location` consumers see the same
names as before. A test that *patches* a name through the shim must patch the
package module instead (section 8); every other consumer is unchanged.

### 3.1 Merge decisions per module

`native_gate`: base is the WSB/Sunset file (newer, hardened). Three DCB-only
behaviours are kept and selected by `native_gate_config.json`:

- `clang_resource` has two shapes. `{"manifest", "manifest_sha256"}` is the
  pinned admission (WSB/Sunset). `{"resource_dir", "required_major",
  "clang_candidates"}` is discovery (DCB, `check_resource` kept). Exactly one
  shape is accepted; `load_config` reports which.
- `read_report` is the DCB strict reader (validates `outcome_summary`,
  `gate_exit in (0,1,3,4)`, blocked assessment keeps `BLOCK`). All four
  products pin the same Gate set hashes (`gate` `01d875b5...`), so the strict
  reader applies to every product. The WSB/Sunset `object_pairs_hook` and
  `parse_constant` guards are kept as well.
- `publications` is optional in the configuration (absent means `[]`), so
  DCB's file needs no change.

`registry`: `maint_config.json` `registry` selects language and the policy
switches in section 1. WSB's hard-coded `passive_include_roots` table becomes a
per-Cell optional key `passive_include_roots` in WSB's `cells.json` (data
migration, section 11). Sunset's `sdk_dependencies` becomes the generic
`registry.sdk_dependencies` block.

`host_build`: gcc response files (DCB) and `CREATE_NO_WINDOW` (WSB) become
common behaviour (both are improvements without product meaning).
`_provider_family`, input receipts, build evidence and SDK link libraries go
through hooks or configuration (sections 4 and 5).

`gate`: Sunset's hardened `_is_link`, `_checked_path`, `_check_tree` and
`quarantine` move to `process.py` and become the common behaviour for every
tool that quarantines a run (also `native_gate`, `cross_build`, `host_build`).
Sunset's Provider `publications` derivation becomes the `gate_publications`
hook.

`cross_build`: the WSB line is covered once `passive_include_roots` is
registry data.

## 4. Product configuration contract

One file per product: `20_ops/tools/maint_config.json`, keys in
`snake_case`, relative repository-anchored paths only, validated fail-closed by
`comsect1_maint.config.load()` before any tool runs. Unknown keys are refused.

```json
{
  "schema": "comsect1.maint_config.v1",
  "product": {
    "id": "dcb",
    "symbol_prefix": "dcb",
    "environment_prefix": "DCB",
    "image_record_product": "dcb"
  },
  "language": "c",
  "registry": {
    "path": "20_ops/tools/cells.json",
    "target_names": ["windows", "arm"],
    "provider_budget_required": "always",
    "owned_library_links_binding": false,
    "membrane_header_exclusions": [],
    "sdk_dependencies": null
  },
  "host_build": {
    "compiler_bin_dir": "C:/msys64/ucrt64/bin",
    "standard_pin": "10_pkg/components/fnd_sdk_standard.json",
    "image_target": "windows-x86_64",
    "provider_family": {
      "kind": "negotiate_offers",
      "offers": [["communication", 2, 1], ["port", 3, 1]]
    },
    "sdk_link_libraries": [],
    "provider_export_aliases": []
  },
  "cross_build": {
    "toolchain_bin_dir": "C:/Program Files/Arm/GNU Toolchain mingw-w64-x86_64-arm-none-eabi/bin",
    "common_flags": ["-ffreestanding", "-fno-builtin", "-Wall", "-Wextra", "-Werror", "-pedantic", "-O2"]
  },
  "native_gate": {
    "config": "20_ops/tools/native_gate_config.json"
  },
  "hooks": null
}
```

Field rules:

| Key | Type | Meaning |
|---|---|---|
| `schema` | const | `comsect1.maint_config.v1` |
| `product.id` | `[a-z][a-z0-9]*` | product word (`dcb`, `hsb`, `wsb`, `sunset`) |
| `product.symbol_prefix` | same pattern | stem prefix: `<prefix>_<cell>`, `<prefix>_provider_<name>_registration`, `<prefix>_<cell>_abi_probe`, fixture `<prefix>_<cell>_<fixture>.dll` |
| `product.environment_prefix` | `[A-Z][A-Z0-9]*` | `external_headers.environment` pattern and `<PREFIX>_<CELL>_LIBRARY` test variables |
| `product.image_record_product` | string | `product` member of `comsect1.image_build_record` |
| `language` | `c` or `rust` | registry schema: `c` requires `standard, definitions, include_roots, freestanding, targets`; `rust` requires `edition` |
| `registry.target_names` | list | admitted `targets` keys (`windows`, `arm`) |
| `registry.provider_budget_required` | `always` or `cross_build_only` | DCB `always`; WSB/Sunset `cross_build_only` |
| `registry.owned_library_links_binding` | bool | WSB `true` (an owned library also links its hosted binding) |
| `registry.membrane_header_exclusions` | list of suffixes | WSB `["_types.h", "_target.h", "_required.h"]` |
| `registry.sdk_dependencies` | null or `{"allowed": [..], "root_environment": "WSB_SDK_ROOT", "required_for_path_prefix": "provider/", "vocabulary_header": "wsb_provider.h", "shell_membrane": "shell/membrane/xpt_wsb_shell.h"}` | Sunset |
| `host_build.compiler_bin_dir` | absolute path | gcc location, child `PATH` only |
| `host_build.provider_family` | `{"kind": "negotiate_offers", "offers": [[family, number, major], ...]}` or `{"kind": "hook"}` | DCB uses offers; WSB and Sunset use the `provider_family` hook |
| `host_build.sdk_link_libraries` | list of `{"environment": "WSB_SDK_ROOT", "member": "lib/windows-x86_64/libwsb_shell.a"}` | Sunset |
| `host_build.provider_export_aliases` | list of symbols | Sunset `["wsb_provider_negotiate", "wsb_provider_open"]`, emitted into the `.def` as aliases of `<stem>_negotiate` / `<stem>_open` |
| `cross_build` | object or null | null in WSB/Sunset/HSB (`cores` empty); object in DCB |
| `native_gate.config` | path | existing per-product file; its own schema is unchanged except the two `clang_resource` shapes |
| `hooks` | null or `{"module": "20_ops/tools/product_hooks.py"}` | section 5 |

The four product values that this schema must express are known (section 1);
the template tests carry one fixture per product shape so that a schema
change that would break a product is caught in the template.

## 5. Product-specific logic: hooks, not forks

`product_hooks.py` is a product-local module loaded by file path. Each hook is
optional; the package calls a hook only when its config requires it and fails
closed when a required hook is missing. Hook names are fixed by the package:

| Hook | Signature | Used by | Today's product code |
|---|---|---|---|
| `provider_family` | `(registration, name) -> str` | `host_build` image records when `host_build.provider_family.kind == "hook"` | WSB `wsb_hosted.registration_family`; Sunset `sunset_package.sdk_archive` + `wsb_policy.hosted` |
| `build_inputs_begin` | `(cell, run_dir) -> token` | `host_build` before compiling a Provider library | Sunset `sdk_input_receipt.validate_sdk_corpus` + `capture` |
| `build_inputs_end` | `(token, cell, library_path, image_record) -> None` | after linking; refuses a changed input, writes the receipt | Sunset `capture` again + `write_receipt` |
| `build_evidence` | `(cell, run_dir, record) -> record` | `host_build` record enrichment | WSB `native_build_evidence`, `_source_dependencies`, `_observed_run` |
| `gate_publications` | `(cell, config) -> list` | `gate.derived_config` | Sunset `publications` from `WSB_SDK_ROOT` |

A hook receives package objects (`registry.Cell`, paths) and may import the
product's own modules. It never receives the package's private state. Anything
that two products need becomes data or package code upstream, not two hooks.

## 6. Template synchronization boundary

Today's practice (read from `.instructions/instruction-layers.md`,
`fork-adoption.md`, the products' `template-origin.json` /
`local/template-baseline.md` and the sync commits `834cee2` HSB, `c7e29bb`
WSB, `2e10034` Sunset): synchronization is a manual three-way merge of the
common files, recorded by updating `template-origin.json`'s `baseline_commit`
and a commit "synchronize the common instructions with <template> <commit>";
`kind/` and `local/` are never touched; no sync tool exists.

This design extends the *common* layer with executable content:

- Common: `20_ops/tools/comsect1_maint/**`, the five entry shims,
  `20_ops/tools/text-format.ps1`. Synced verbatim (copy, not merge): a product
  never edits them. A local edit is a defect; the fix goes upstream.
- Local: `20_ops/tools/maint_config.json`, `cells.json`,
  `native_gate_config.json`, `product_hooks.py`, every other `20_ops/tools/*`
  file. Never written by synchronization.

`comsect1_maint/sync_manifest.json` lists every common file with its sha256
(`{"schema": "comsect1.maint_sync_manifest.v1", "files": {"comsect1_maint/registry.py": "<sha256>", "native_gate.py": "<sha256>", ...}}`),
generated by `python -I -B 20_ops/tools/comsect1_maint/sync.py --write-manifest`
in the template. In a product, `python -I -B 20_ops/tools/comsect1_maint/sync.py --check`
verifies the common files against the manifest and reports `MODIFIED`,
`MISSING` or `EXTRA` paths (exit 1). `sync.py --from <template-checkout>`
copies the common layer from a template checkout, refuses links, writes
nothing outside the listed paths, and prints the new baseline commit for
`template-origin.json`. Both are standard-library Python.

Template instruction changes that accompany the package (common files):

- `instruction-layers.md`, "Template synchronization boundary": add the
  executable common layer and its local counterpart as listed above.
- `fork-adoption.md` item 11: synchronization also copies
  `20_ops/tools/comsect1_maint/` and the entry shims; the fork writes
  `maint_config.json` and, if needed, `product_hooks.py`.
- `artifact-placement.md`: one row, "Template-owned maintainer tool package
  and its tests | `20_ops/tools/comsect1_maint/`" (the tests travel with the
  package because they are common-layer content, the one exception to
  "test source in `10_pkg/`").
- `development-feedback-and-release-evidence.md`: the fast-feedback operation
  for the tools is `python -I -B -m unittest discover -s 20_ops/tools/comsect1_maint/test`.

### 6.1 Comsect1 and Hatbit templates

`comsect1-project-template` owns `comsect1_maint`. The Hatbit template
already declares Comsect1 as its upstream (`template-origin.json`
`baseline_commit 99f9335`), so Hatbit receives the package through its own
template synchronization and never edits it; a Hatbit need (firmware layering,
CMake presets per `development-workflow-integration.md`) is expressed by a
product's configuration or hooks, or proposed upstream. `text-format.ps1`:
adopt Sunset's untracked-file scan in the Comsect1 template first, then let
Hatbit sync it, so the three copies converge on one text again.

## 7. Versioning by template revision

The package carries no version of its own. The product's
`.instructions/template-origin.json` (`baseline_commit`) is the single record
of which template revision the common layer came from; `comsect1_maint.origin()`
reads it. Every tool run summary (`native_gate` `summary.json`, `host_build`
`build_record.json`, `cross_build` and `gate` records) gains one member
`"maintainer_tools": {"template": "<name>", "baseline_commit": "<sha>", "manifest_sha256": "<sha>"}`.
A run fails closed with the config exit class when `template-origin.json` is
absent or the manifest check reports a modified common file, unless
`--accept-tool-drift` is given (the same pattern as `native_gate`'s existing
`--accept-tool-hashes`), in which case the summary records
`"tool_drift_accepted": true`. DCB and HSB currently have no
`template-origin.json` (they record the baseline in
`local/template-baseline.md`); migration adds the file.

No `r{n}`, `v1`/`v2` or date appears in a package path, module name or
identifier (version policy); the schema ids follow the template's existing
`comsect1.<name>.v1` form.

## 8. Test plan

Template-owned tests (`20_ops/tools/comsect1_maint/test/`, standard-library
`unittest`, run with `python -I -B -m unittest discover -s 20_ops/tools/comsect1_maint/test`
from the template or any product):

- `path_guard`, `process`: link/junction refusal, `checked_path` on
  drive-relative and `..` input, `quarantine` inventory and inode checks,
  `run_process` timeout kill (fixture scripts under `test/fixtures/`).
- `config`: every example config (`fixtures/config/{dcb,hsb,wsb,sunset}.json`)
  loads; one negative case per rule (unknown key, absolute path, wrong
  language keys, missing hook when required).
- `registry`: C and Rust fixture registries; each policy switch exercised in
  both states; `passive_include_roots`, `sdk_dependencies`, `fixture_units`.
- `native_gate`: `load_config` accepts each `clang_resource` shape and refuses
  a mixed one; `read_report` (moved from WSB/Sunset `test_native_gate_report.py`,
  extended with DCB's `outcome_summary` cases); toolchain admission (moved
  from WSB `test_native_gate_toolchain.py`); input owners (moved from WSB
  `test_native_input_owners.py`).
- `cross_build` selection and `host_build` pure helpers (`header_functions`,
  `_exported_names`, `_strip_comments`, `_response_file`, `.def` aliases).
- `sync`: manifest write/check round trip; a modified file is reported.

Product tests, unchanged in behaviour:

- Each product's existing commands keep running exactly as listed in its
  `local/c-build-and-test.md` (DCB: `10_pkg/test/tool/gate`, `.../registry`,
  `.../build`; WSB: `10_pkg/test/tool/{gate,registry,build,package}`; Sunset:
  `10_pkg/test/tool/gate`; HSB: `10_pkg/test/python/...`). They load the
  shims by path and call public functions; no change.
- The only required edit: tests that patch a module global through the shim
  (`patch.object(driver, 'sha256_file')`, `driver._path_guard`) must patch
  `comsect1_maint.native_gate` instead. Known files: WSB
  `10_pkg/test/tool/gate/test_native_gate_report.py`, Sunset
  `10_pkg/test/tool/gate/test_native_gate_report.py` and
  `10_pkg/test/tool/native_gate/test_native_gate_report.py` (duplicate; delete
  one). After the template owns these cases (above), the product copies may be
  removed in the same product commit.
- Acceptance per product: the set of passed and skipped test ids before and
  after migration is identical (record both lists in
  `20_ops/06_verification/maintainer_tools_migration.md` of the product).

Behaviour equivalence per product: run `gate.py --cell <cell> --target windows`,
`native_gate.py` on one Cell, `build.py --cell <cell>` and (DCB)
`cross_build.py --archive` before and after; diff `summary.json` /
`build_record.json` ignoring `run_id`, timestamps and the new
`maintainer_tools` member. Expected deltas are only those listed in section 11.

## 9. Boundary to the common SDK tool (T1)

`fnd-sdk-standard` `10_pkg/sdk_tool/comsect1_sdk_tool` builds
`tools/comsect1_sdk.pyz`, shipped in every SDK (DCB, HSB, WSB, Sunset, Gantry,
Eschaton) for SDK *users* (`install-sdk`, `bundle-runtime`). `comsect1_maint`
is for *maintainers* and is never shipped: it is not a recipe input, never
appears in an SDK or RUNTIME deliverable, and contains no install or bundle
logic. Keep the two apart by rule, not by inspection: each product's
`package.py` already scans shipped files; it must additionally refuse any
path under `20_ops/`. The Foundation tool is pinned per product through
`component-pins.md`; `comsect1_maint` is versioned by template baseline
(section 7). The two have no import relation in either direction.

## 10. Out of scope, recorded

- `package.py` (DCB, HSB, WSB): too divergent for T2. A later increment can
  extract its 66 identical units (`_digests`, `_refuse_links`, `path_problem`,
  `tag_name`/`tag_id`, `render_tag`, `render_redistributable`, `_spdx_id`,
  `scan`, `query_identity_line`, `issue_deliverable`) into
  `comsect1_maint/release.py` once the three products agree on one recipe
  model.
- `wsb_evidence.py`, `wsb_project.py` (DCB, HSB): WSB consumer tools, copied
  by the two adopters of the WSB SDK. They are SDK-user content and belong in
  the WSB SDK (`sdk` content), not in the project template. Record as a WSB
  finding.
- HSB `build.py` and `gate.py` (cargo and Rust Gate drivers) stay local; they
  adopt `comsect1_maint.process` and `registry` (Rust mode) only.

## 11. Per-product deltas

| Product | Removed (copied lines) | Added locally | Behaviour deltas on adoption |
|---|---|---|---|
| DCB | `native_gate.py` 707, `cross_build.py` 272, `cell_registry.py` 603, `build.py` 818, `gate.py` 135 = 2,535 (replaced by 5 shims, ~70) | `maint_config.json` (~45 lines; `provider_family` as `negotiate_offers`, no hook), `template-origin.json` | path guard now refuses linked or reparse paths in Cell and include roots; hardened quarantine; `publications` and toolchain-manifest mode available but not selected; `maintainer_tools` member in records |
| HSB | `cell_registry.py` 131 (Rust mode of `registry`, shim ~14); ~60 duplicated helper lines in `build.py`/`gate.py` (`is_reparse`, `quarantine_run`, `_load_sibling`, `new_run_id`) replaced by `process` imports | `maint_config.json` (`language: rust`, no `host_build`/`cross_build`/`native_gate`), `template-origin.json` | none in cargo or Gate behaviour; hardened quarantine |
| WSB | `native_gate.py` 883, `native_path_guard.py` 30, `cross_build.py` 272, `cell_registry.py` 627, `build.py` 844, `gate.py` 136 = 2,792 | `maint_config.json` (~50; `provider_family` hook, `build_evidence` hook), `product_hooks.py` (~25, delegating to `wsb_hosted` and `native_build_evidence.py`), `cells.json` gains `passive_include_roots` on `shell`, `process`, `report`, `binder`, `host`, `windows`, `abi` | strict `read_report` (`outcome_summary` required; same Gate set, so no new failures expected); gcc response files; hardened quarantine; `fixture_units` kept |
| Sunset | `native_gate.py` 883, `native_path_guard.py` 30, `cross_build.py` 272, `cell_registry.py` 627, `build.py` 783, `gate.py` 225 = 2,820 | `maint_config.json` (~55; `sdk_dependencies`, `sdk_link_libraries`, `provider_export_aliases`, `provider_family` hook), `product_hooks.py` (~45: `provider_family` via `sunset_package.sdk_archive`, `build_inputs_begin/end` via `sdk_input_receipt.py`, `gate_publications`) | strict `read_report`; gcc response files; its hardened quarantine becomes common (no change for Sunset) |

Total copied lines retired: about 8,300 across the four products; package
size about 3,300 plus tests.

## 12. Risks

1. DCB is being committed to by another session (2026-11-02). Land the
   template first; migrate DCB only on a quiet working tree, in one commit.
2. The strict `read_report` is applied to WSB and Sunset. Mitigation: all
   products pin the identical Gate set hashes; the template test carries both
   report shapes; if a product's Gate set ever lacks `outcome_summary`, the
   fix is a Gate set update, not a reader relaxation.
3. Path guard in DCB: a developer checkout reached through a junction (for
   example a short-path link) will be refused. This is the intended fail-closed
   rule (`temporary-output-and-cleanup.md`); record it in DCB's
   `c-build-and-test.md`.
4. Two `clang_resource` modes keep DCB's discovery alive. Recommend DCB adopt
   the manifest mode as a follow-up owner decision; until then both modes are
   tested in the template.
5. Tests that patch through the shim silently stop patching if the one-line
   repoint is missed; the template test `test_shims.py` asserts that each shim
   exposes the same public names as its package module, and the product
   acceptance (section 8) compares test id sets, so a changed outcome shows.
6. WSB `passive_include_roots` moves from code to `cells.json`; a missed Cell
   changes WSB's include set. Mitigation: the migration commit diffs the
   derived `include` lists per Cell before and after (behaviour equivalence
   run).
7. `sys.path.insert` in the shim exposes `20_ops/tools/` to imports; with
   `python -I` and no `__init__.py` beside the package, only `comsect1_maint`
   is importable as a package; the entry shims remain file-loaded modules.
8. Sync without a tool today: `sync.py --check` is the first machine check of
   the common layer in a product; until it exists, drift can only be found by
   diff. Implement `sync.py` in the template before the first product
   migration.
9. Hatbit convergence: if Hatbit is not synced promptly, Sunset would carry
   the package ahead of its own template. Order Hatbit's sync before Sunset's
   migration (section 13).

## 13. Implementation steps

Template (`comsect1-project-template`, branch work in a scratchpad worktree
per the shared-checkout rule; one PR):

1. Create `20_ops/tools/comsect1_maint/` with `path_guard.py` (copy of WSB
   `native_path_guard.py`) and `process.py` (extract the helpers named in
   section 1; use the Sunset `_is_link`, `_checked_path`, `_check_tree`,
   `quarantine`; DCB `run_process`/`kill_tree` from `native_gate.py`).
2. Write `config.py`: load `maint_config.json`, enforce the section 4 schema,
   load `product_hooks.py` by file path, read `template-origin.json`,
   verify `sync_manifest.json`, expose `origin()`.
3. Port `registry.py` from WSB `cell_registry.py` (the superset), replace the
   product terms with `config.product.*`, add the policy switches, make
   `passive_include_roots` a Cell key, make `sdk_dependencies` generic, add the
   Rust mode from HSB `cell_registry.py`.
4. Port `native_gate.py` from WSB (3.1): both `clang_resource` shapes, DCB
   strict `read_report`, optional `publications`, `process` helpers.
5. Port `cross_build.py` (DCB/Sunset text), `host_build.py` (WSB text plus
   DCB response files, hooks of section 5, `provider_export_aliases`,
   `sdk_link_libraries`), `gate.py` (Sunset text, `gate_publications` hook).
6. Write the five entry shims and `sync.py` (`--write-manifest`, `--check`,
   `--from`); generate `sync_manifest.json`.
7. Move the WSB/Sunset/DCB tool tests into `comsect1_maint/test/` as listed
   in section 8, add the config fixtures for the four product shapes and
   `test_shims.py`; run `python -I -B -m unittest discover -s 20_ops/tools/comsect1_maint/test`
   on a clean checkout (no product present): all pass.
8. Update the four common instructions named in section 6 and adopt Sunset's
   `text-format.ps1` improvement. Run `text-format.ps1`. Commit, PR, merge;
   note the merge commit as the new baseline.

Products, in this order; each is one commit "chore(tools): adopt the template
maintainer tools at <baseline>", preceded by the before-run of section 8:

9. DCB: `sync.py --from <template>`; write `maint_config.json`
   (`negotiate_offers` from `_FAMILY_OFFERS`, `target_names` with `arm`,
   `provider_budget_required: always`, `cross_build` block from
   `cross_build.py` constants); add `.instructions/template-origin.json`
   (baseline from `local/template-baseline.md`, updated); delete the five
   product copies (shims replace them); run the DCB tool and Cell test
   commands; after-run and equivalence diff; record in
   `20_ops/06_verification/maintainer_tools_migration.md`; update
   `local/c-build-and-test.md` (path guard note) and `local/template-baseline.md`.
10. HSB: sync; `maint_config.json` with `language: rust`; replace
    `cell_registry.py` by the shim; in `build.py` and `gate.py` replace the
    duplicated helpers with `comsect1_maint.process` imports; add
    `template-origin.json`; run the HSB suites; record.
11. WSB: sync; `maint_config.json` (`provider_family: hook`,
    `cross_build_only`, exclusions, `owned_library_links_binding: true`);
    `product_hooks.py` (`provider_family` -> `wsb_hosted.registration_family`,
    `build_evidence` -> `native_build_evidence.py`); add
    `passive_include_roots` to the seven Cells in `cells.json`; delete the six
    product copies; repoint `test_native_gate_report.py` patches or delete the
    cases now owned by the template; run; equivalence diff of per-Cell include
    lists; record.
12. Hatbit template: synchronize from Comsect1 (common instructions,
    `comsect1_maint`, shims, `text-format.ps1`); update its
    `template-origin.json`.
13. Sunset: sync from Hatbit; `maint_config.json` (`sdk_dependencies`,
    `sdk_link_libraries`, `provider_export_aliases`, `provider_family: hook`);
    `product_hooks.py` (section 11); delete the six product copies and the
    duplicate report test; run; record; update `template-origin.json`.
14. Close T2 in `fnd-architecture` section 8 with the baseline commit and the
    four product commits; open the two section 10 findings (package.py
    release helpers; WSB consumer tools as SDK content).
