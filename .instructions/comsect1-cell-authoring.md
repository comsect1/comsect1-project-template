# Comsect1 Cell Authoring Model

This instruction is complete for ordinary Cell authoring and refactoring. Do
not consult another repository to decide a zone, role, classification, prefix,
or local control-file placement.

## One local control authority

`comsect1.json` is the only Comsect1-authored control file inside a Cell. It
contains only facts that a tool cannot derive from the governed tree, such as
Cell kind, languages, public identity surfaces, selected conventions, feature
roots, and explicitly intended semantic relations.

Do not create or update any of the following:

- `contract/projection/<language>/metadata.json`;
- `contract/convention/contract_convention_activation.json`;
- `comsect1-role:`, `SSOT:owner`, `deps:`, or other Comsect1-only source
  comments; or
- a language-specific Cell control file beside `comsect1.json`.

Gate may inspect the actual governed files as its subject. Its language rules
and profiles belong to the installed tool, and its derived inventory,
projection, observations, findings, and evidence belong outside the Cell.
Product-owned JSON contracts and runtime configuration remain ordinary product
artifacts; this rule forbids additional Comsect1 control surfaces, not JSON as
a medium.

## Gate and Forge execution

- Gate is read-only. At runtime it derives each declared Cell's governed
  inventory from the local `comsect1.json` and immutable tree, then emits a
  concise, issue-oriented result: diagnostics or non-PASS Cells,
  correction/review candidates, and summary counts. Do not copy successful
  full evidence into logs or invent a cache, sidecar, or local metadata file
  to remember a scan.
- `--events` emits bounded transient item progress on standard error. It
  creates no lifecycle, action, approval, or run state.
- Forge may plan only from structured, snapshot-bound Gate mechanical
  authority. Its bounded progress never grants repair authority; a
  same-criteria Gate reassessment decides the resulting Cell verdict.

## Three independent decisions

Choose a zone, a semantic role when applicable, and a classification in that
order. They are separate axes. A prefix never creates authority, a dependency,
an access exception, or a call hierarchy. When a parser-proven governed
role-to-role consumption edge exists, it may remain within one role or move
only `src_ -> med_ -> rea_`; reverse consumption is forbidden.

| Zone | Admitted prefixes | Responsibility |
|---|---|---|
| `core/` | `src_`, `med_`, `rea_` | Feature meaning and its dependent role family |
| `core/` | `cfg_`, `db_` | Governed configuration and data without a semantic role |
| `contract/` | `contract_` | Passive promises, shapes, and shared vocabulary |
| `membrane/` | `api_` | Consumer-addressable surface of this Cell |
| `capability/` | `stm_` | Cross-feature runtime state, events, and streams |
| `capability/` | `svc_`, `mdw_`, `hal_`, `bsp_` | Role-less service, pipeline, and hardware facilities |

All four zone directories exist at the Cell root. A Cell does not gain another
zone from a language, framework, package layout, or prefix.

## Core role families

For one lower-snake-case stem `S`, `src_S` is the sole semantic owner.
`med_S` and `rea_S` are optional sibling dependents in the same feature root;
they are not stages in a required `src -> med -> rea` call chain.

- `src_` owns decisions, policy, invariants, domain meaning, state-transition
  rules, validation criteria, and interpretation of the Cell's promises. It
  keeps that ownership when it calls a library, driver, protocol, or platform.
- `med_` maps between two named semantic representations while preserving the
  meaning already owned by its `src_`. It owns neither product policy nor an
  irreversible effect. Syntax helpers and thin boundary wrappers are not
  mediation merely because they translate bytes or types.
- `rea_` performs, orchestrates, persists, publishes, or otherwise carries out
  already-decided behavior. It may execute an already-owned validation rule,
  but it must not choose the rule, default, policy, or sole meaningful service
  behavior.

A dependent replaces only the prefix of its exact SOURCE stem. Optional leaves
use `med_S_<subtype>` or `rea_S_<subtype>`. Within each dependent role, an
unsplit parent and its split children cannot coexist: use either `rea_S` or
leaves such as `rea_S_read` and `rea_S_write`, never all three. Mediation and
realization split independently.

Filename and physical sibling placement provide the mechanical family
identity. `comsect1.json` declares only non-derivable feature roots or semantic
relations; it does not repeat every artifact, path, symbol, role, or observed
call.

## Role-less surfaces

- `contract_` is passive. Executable behavior, mutable state, orchestration,
  and policy do not belong in `contract/`.
- `api_` is exclusively outward-facing. A Cell's own Core and capabilities do
  not call its membrane as an internal acquisition path.
- `cfg_` and `db_` are governed material, not disguised SOURCE owners.
- `stm_`, `svc_`, `mdw_`, `hal_`, and `bsp_` are classifications, not roles.
  They do not form a promotion ladder or imply allowed dependency directions.
- A cross-feature interaction uses a role-less seam selected by meaning:
  shared state through `stm_`, shared shapes through `contract_`, explicit
  composition through a Core composition table, and an independently justified
  mechanism through a capability. A forwarding wrapper is not a seam.
- Another Cell is consumed only through its `api_` membrane surface.

## Required decision procedure

Before creating, moving, or renaming an artifact:

1. Identify the exact Cell and the responsibility it owns.
2. Select the zone from that responsibility, not from the file type.
3. If it is feature meaning, identify the feature root and its one `src_`
   owner.
4. Add `med_` only for a named meaning-preserving representation mapping.
5. Add `rea_` only for an effect whose policy remains in the sibling `src_`.
6. Otherwise select the truthful role-less surface; do not invent a SOURCE to
   justify a prefix.
7. Record only non-derivable intent in `comsect1.json`.
8. Reject a change that merely relabels, re-exports, forwards, or moves an edge
   to silence a finding.

A meaningful `src_controller` that decides retry policy may call a replaceable
`rea_controller_transport`; moving the retry policy into the realization and
leaving a forwarding SOURCE is invalid. A `med_controller_frame` is justified
only when it maps a named controller representation to a named frame
representation without choosing retry or transport behavior.

## Design-before-edit refactoring closure

Before a semantic Cell refactor, derive these work products outside the Cell
from its public contract, relevant specification, governed tree, and baseline
Gate evidence:

1. public meaning, state flow, behavior invariants, and external effects;
2. the semantic owner map across Core roles and truthful role-less seams;
3. the expected governed dependency graph and exact SOURCE-stem lineage;
4. external isolation boundaries and public identity surfaces; and
5. behavior, role-pack, complete Cell, and direct-consumer acceptance checks.

Complete this design before moving implementation. Gate confirms the resulting
AST-observed structure; a lower finding count does not substitute for the
design. Treat any changed finding class, new unresolved observation, missing
SOURCE lineage, SOURCE-owned effect, MEDIATION-owned policy, reverse
REALIZATION consumption, active contract, internal membrane acquisition, or
forwarding seam as an incomplete refactor.

After editing, run behavior verification, the Gate pack that exposed the
issue, the complete Cell Gate, and affected direct-consumer tests. Keep the
derived maps and transient evidence in the task-owned run outside every Cell;
do not turn them into another control file or persist derived relations in
`comsect1.json`.
