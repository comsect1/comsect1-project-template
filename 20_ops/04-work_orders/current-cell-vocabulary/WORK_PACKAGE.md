# Work Package: Current Cell vocabulary synchronization

Status: `done`
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

## Result (2026-09-26)

`.instructions/comsect1-cell-authoring.md` is replaced as one piece by the
Specification's authoring model at `comsect1-architecture` `5d4dd65`. That
model includes the prohibited-stem rule, the adopted-library law, required
operations and the design-before-edit closure. It is written in this public
template's tool-neutral wording: structural verification and analysis, with
no internal tool names or execution section. `refactoring-and-updates.md`
names semantic-owner lineage. A retired-prefix search over `.instructions/`,
`AGENTS.md` and `README.md` finds only the prohibited-stem statement, which
is the rule itself. `20_ops/tools/text-format.ps1` passes. P4 was resolved by
committing the pending edits (`40b540b`).
