# Version and Compatibility Policy

This policy is a core project invariant. It prevents temporary development
history from becoming permanent product structure or an accidental external
contract.

## Authorities

- An official release version is valid only when assigned by the project's
  explicit release authority and recorded in the release boundary.
- A work revision such as `r{n}` identifies an internal review or work record.
  It is not a product version, compatibility promise, schema generation, or
  behavioral input.
- A commit identifier records source history. It does not authorize runtime or
  build-time branching by historical state.

Do not substitute one authority for another. In particular, do not promote a
work revision, branch name, milestone, blueprint revision, or temporary test
label into product semantics.

## Prohibited history-driven design

Do not encode `legacy`, `old`, `previous`, `v1`, `v2`, `r{n}`, dates, migration
waves, or equivalent labels in:

- implementation types, functions, modules, macros, constants, or feature flags;
- source, package, asset, configuration, or generated-output paths;
- schemas, protocols, persisted formats, cache keys, or behavior selectors;
- build targets, deployment modes, tests, fixtures, or permanent comments; or
- aliases, wrappers, adapters, routing rules, or dependency-injection choices.

A domain term that happens to contain a number is allowed only when the number
is part of the current external domain meaning, not a disguised development
generation. Official release metadata is allowed at its authorized boundary.

An internal `r{n}` may appear in a work order, review note, issue, or other
non-normative traceability record. Prefer the record's name or metadata over
source comments. It must never change what is built, loaded, stored, or run.

## Pre-release replacement rule

Before an official release establishes an approved external compatibility
obligation, refactoring is a full current-state replacement. Remove superseded
code and update its tests, fixtures, build configuration, schemas, examples, and
documentation together.

Do not introduce or retain a compatibility seam, shim, adapter, facade, wrapper,
alias, fallback, feature flag, dual implementation, migration path, or data
translator merely to preserve temporary, experimental, test-only, or unreleased
behavior. A seam is justified only by a current responsibility boundary or a
real external contract; historical convenience is not a boundary.

## Post-release compatibility exception

Compatibility after an official release is not automatic. Before adding it,
record all of the following in an authorized blueprint or release decision:

1. the released external contract and affected consumers;
2. the approving authority and boundary owner;
3. the exact behavior, data, protocol, or API scope;
4. the support period and verification obligations; and
5. the retirement trigger or explicit continuation decision.

Place approved compatibility logic at the owned external boundary. Do not let
it fork the internal architecture into permanent historical generations.

## Refactoring review

Treat history-driven names and compatibility machinery as findings. Review code,
configuration, schemas, paths, build inputs, tests, fixtures, and documentation.
Remove obsolete branches rather than renaming them to a newer generation.
Preserve history in Git and lifecycle records, not in production structure or
permanent explanatory comments.
