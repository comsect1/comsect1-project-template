# Lifecycle and Traceability

The numbered `20_ops/` directories provide a readable V-shaped information flow
without encoding `v-model` in a path or mandating one named process.

```text
inputs -> requirements -> blueprints -> work orders -> development
                                      -> verification / validation
                                      -> traceability -> assurance -> release
```

Keep plans, working evidence, findings, dispositions, and readiness preparation
together in `20_ops/`. Keep executable test source in `10_pkg/`, raw runs in
`90_temps/`, and only issued final credentials in `30_cert/`.

Execution success, test outcome, V&V conclusion, baseline approval, readiness,
and release authorization are distinct states and must not be inferred from one
another. Retained records bind the exact subject snapshot and input revisions.
