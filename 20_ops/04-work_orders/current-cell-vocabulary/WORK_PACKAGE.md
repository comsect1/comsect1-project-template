# Work Package: Current Cell vocabulary synchronization

Status: `draft`
Work package ID: `current-cell-vocabulary`
Owner: `comsect1`
Owned paths: `.instructions/comsect1-cell-authoring.md`, `.instructions/refactoring-and-updates.md`, `.instructions/README.md`, `AGENTS.md` Cell authoring section
Read-only inputs: `comsect1-architecture` `6918eab` Specification and its `.instructions/comsect1-cell-authoring.md`; `20_ops/03-blueprints/current-cell-vocabulary/DESIGN_DIRECTIVE.md`
Expected outputs: common instructions that state the current prefix vocabulary and the laws in the design directive, with no retired prefix remaining
Verification: `20_ops/tools/text-format.ps1`; a retired-prefix text search over `.instructions/` and `AGENTS.md` returns nothing outside the design directive's mapping table
Negative cases: a partial rewrite that mixes vocabularies; a compatibility note or alias for retired prefixes in a common file; product-level layering copied into this vendor-neutral template
Handoff criterion: the common Cell authoring model matches the Specification, and `hatbit-project-template` can sync from the resulting commit

Date: 2026-09-26.

This package is prerequisite P3 of the Comsect1 Architecture work order
`20_ops/04-work_orders/cell-conformance-migration/WORK_ORDER.md`. Execute it
as one complete replacement, after the uncommitted instruction edits found in
this template's main working tree on 2026-09-26 are resolved by their owner
(prerequisite P4).
