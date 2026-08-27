# Artifact Placement

| Material | Location |
|---|---|
| Authored implementation, test code, fixtures, build inputs | `10_pkg/` |
| Inputs and constraints | `20_ops/01-inputs/` |
| Requirements and acceptance criteria | `20_ops/02-requirements/` |
| Architecture, design, and decisions | `20_ops/03-blueprints/` |
| Bounded work packages | `20_ops/04-work_orders/` |
| Development plans and receipts | `20_ops/05-development/` |
| Verification plans, cases, and reviewed results | `20_ops/06-verification/` |
| Validation plans, scenarios, and reviewed results | `20_ops/07-validation/` |
| Baselines, links, coverage, and gaps | `20_ops/08-traceability/` |
| Findings, dispositions, and readiness preparation | `20_ops/09-assurance/` |
| Packaging and release preparation | `20_ops/10-release/` |
| Executable tool scripts, build helpers, and runners | `20_ops/tools/` |
| Auxiliary dotfiles, third-party configs, and tool presets | `.configs/` (e.g., `.configs/cmake/`, `.configs/meridian/`) |
| Raw output, caches, traces, screenshots, staging | `90_temps/` |
| Issued immutable final packages | matching numbered `30_cert/` directory |

Raw output is not retained evidence merely because it exists. A reviewed
record in `20_ops/` binds stable IDs, relative locators, manifests, and digests.
Only an authorized issue operation creates a final package in `30_cert/`.
