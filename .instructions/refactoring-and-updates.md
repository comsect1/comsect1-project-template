# Unit Repository Refactoring and Updates

This guide applies only to a unit repository. It does not define umbrella
membership or category structure.

## Invariants

- Preserve external behavior unless an authorized decision in
  `20_ops/03-blueprints/` changes it.
- Preserve only an identified external contract. Unreleased, temporary, and
  test-only behavior has no compatibility claim and must not justify a seam,
  shim, adapter, alias, wrapper, dual implementation, or migration branch.
- Do not retain arbitrary version, revision, `legacy`, `old`, or `v1`/`v2`
  labels in source, paths, configuration, schemas, or behavioral selectors.
- Keep authored implementation, executable tests, fixtures, and build inputs in
  `10_pkg/`; do not force a language-independent internal package tree.
- Keep passive tool configuration in `.configs/` and executable project helpers
  in `20_ops/tools/`.
- Use only relative, repository-anchored paths.
- Put raw build and verification output in a task-owned `90_temps/` run.
- `comsect1.json` is the only Cell-local Comsect1 control authority. Do not add
  projection sidecars, convention activation files, or control comments.

## Refactoring sequence

1. Record scope and behavior invariants in `20_ops/04-work_orders/`. Identify
   any authorized released external contract; absence means current-state
   replacement, not compatibility work.
2. Freeze the current baseline and run existing verification under
   `90_temps/verification/<run-id>/`.
3. Refactor the natural implementation layout inside `10_pkg/`, remove the
   superseded implementation, and update tests, fixtures, build inputs, and
   documentation to the single current state. Update only non-derivable Cell
   intent in `comsect1.json`.
4. Audit identifiers, macros, flags, aliases, paths, schemas, persisted formats,
   and comments for history-driven version control. If approved post-release
   compatibility exists, confine it to the owned external boundary and record
   its support and retirement decision.
5. Classify durable guidance discovered during the refactor as common, kind, or
   local. Put project-specific guidance in `.instructions/local/`; do not turn a
   work-order decision into permanent common guidance by copying it into root
   instruction files or `AGENTS.md`.
6. Verify behavior, dependency licenses, Cell structure, and relative paths.
   Run `20_ops/tools/text-format.ps1` before Gate so working-tree byte drift is
   reported independently of architecture findings.
7. Record reviewed results in `20_ops/`; issue a package into `30_cert/` only
   through an authorized finalization step.
8. Clean the exact task-owned run through `99_trash/`.
