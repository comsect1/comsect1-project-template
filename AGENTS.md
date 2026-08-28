# Comsect1 Project Template Instructions

## Authority

- This repository is a forkable project scaffold, not a Comsect1 Specification.
- The local Cell authoring model below governs every declared Cell in an
  ordinary authoring or refactoring task.
- Project-folder placement outside Cells is non-normative guidance.
- Never infer a Cell from `10_pkg/`, a folder name, or repository membership; only
  a local `comsect1.json` establishes Cell identity.

## Cell authoring baseline

- [Cell authoring model](./.instructions/comsect1-cell-authoring.md) is the
  complete local decision model for Cell control authority, zones, roles,
  classifications, prefixes, and refactoring. Read it before changing a Cell.
- `comsect1.json` is the only Cell-local Comsect1 control authority. Do not
  create projection sidecars, convention activation files, or Comsect1-only
  source comments.

## Required project shape

- Preserve the complete template folder tree, including placement directories
  that are not yet populated.
- `10_pkg/` owns authored implementation, executable test source, fixtures, and
  build-consumed inputs.
- `20_ops/01-inputs/` through `20_ops/10-release/` own one continuous preparation,
  development, verification, validation, traceability, assurance, and release
  process.
- `30_cert/01-verification/` through `30_cert/04-release/` contain only explicitly
  issued, immutable final credential packages.
- `90_temps/` is the only disposable generation root. `99_trash/` is the only
  cleanup quarantine.
- Language, compiler, package-manager, test-runner, and platform bindings must
  be defined by this fork's own instructions; do not present them as Spec law.
- Repository-authored text follows [the text-format policy](./.instructions/text-format-policy.md).
  Validate it with `20_ops/tools/text-format.ps1`; use its explicit `-Apply`
  mode for an unstaged byte-format correction.

## Temporary-output mandate

- Create every transient output below one exact task-owned
  `90_temps/<class>/<tool-or-purpose>/<run-id>/` directory.
- A task is incomplete while its owned temporary output remains.
- Promote only compact reviewed records to `20_ops/`; issue material into `30_cert/`
  only through an authorized finalization step.
- Close producers, resolve and preview exact paths, reject links and reparse
  escape, move the exact run directory to a new `99_trash/<cleanup-id>/`, verify
  it, and delete only that exact quarantined child.
- Never recursively delete `10_pkg/`, `20_ops/`, `30_cert/`, `90_temps/`, `99_trash/`, a
  repository root, a workspace root, a Cell root, or an unresolved path.
- Never delete unknown, shared, dirty, or another task's output.

## Routed instructions

- [Instruction index](./.instructions/README.md)
- [Artifact placement](./.instructions/artifact-placement.md)
- [Lifecycle and traceability](./.instructions/lifecycle-and-traceability.md)
- [Temporary output and cleanup](./.instructions/temporary-output-and-cleanup.md)
- [Fork adoption](./.instructions/fork-adoption.md)
- [Licensing policy](./.instructions/licensing-policy.md)
- [Refactoring and updates](./.instructions/refactoring-and-updates.md)
- [Text format policy](./.instructions/text-format-policy.md)
