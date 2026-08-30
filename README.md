# Comsect1 Project Template

Fork this repository to start a project with the same non-normative project
folder-tree baseline. The scaffold separates authored inputs, the continuous
development and assurance process, issued credentials, disposable output, and
cleanup quarantine.

This repository is the upstream SSOT for the unit-repository scaffold, local
Cell-authoring instructions, and template licensing policy.

The folder tree does not create Comsect1 conformance. A directory becomes a
Cell only through its own `comsect1.json`, and the current Comsect1 architecture
publication remains authoritative for that Cell.

After a fork, complete `.instructions/fork-adoption.md` before implementation.

## Gate-to-Forge execution kernel

```text
Cell root and comsect1.json
-> complete immutable runtime inventory
-> language AST and binding
-> normalized proven observations
-> current Gate issues with exact AUTO_FIX candidates and direct rework IDs
-> selected AUTO_FIX: ephemeral exact plan -> apply -> same-Gate result
-> no selected mutation: initial Gate result remains current
-> current direct REWORK IDs labeled by --ai-rework on|off
```

For each locally declared Cell, run `comsect1-gate check --root <cell>`. Gate
and Audit are read-only and persist only caller-selected external issue output.
Run `comsect1-forge fix --root <cell> --ai-rework <on|off>` when Gate identifies
the correction flow. Forge applies exact mechanical candidates without
approval, reruns the same Gate, and labels only the remaining direct rework IDs;
it never launches AI. Unit roots remain `10_pkg/`, `20_ops/`, `30_cert/`,
`90_temps/`, and `99_trash/`; umbrella classification groups do not apply.

---

## Author & Architecture Governance

- **Creator & Principal Architect**: Kim Hyeongjeong ([@comsect1](https://github.com/comsect1))
- **Architecture Standard**: Comsect1 Architecture
- **License**: Apache-2.0 with Comsect1 Template Instantiation Exception (See [`LICENSE.md`](./LICENSE.md) and [`NOTICE.md`](./NOTICE.md))
