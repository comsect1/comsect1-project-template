# Current Cell vocabulary design directive

Date: 2026-09-26.

Authority: owner direction of 2026-09-26 to carry the decided Comsect1 context
into the templates, and the Comsect1 Specification at `comsect1-architecture`
`6918eab`.

## Direction

A repository created from this template starts on the current Comsect1 prefix
vocabulary and laws. The common Cell authoring model states them; work package
`20_ops/04-work_orders/current-cell-vocabulary/WORK_PACKAGE.md` carried the
replacement.

## Prefix vocabulary

| Zone | Current prefixes | Retired prefixes they replace |
|---|---|---|
| `core/` | `smo_`, `rmp_`, `efx_` | `src_`, `med_`, `rea_` |
| `core/` | `cfg_`, `dat_` | `cfg_`, `db_` |
| `contract/` | `pvo_` | `contract_` |
| `membrane/` | `xpt_` | `api_` |
| `capability/` | `csr_` | `stm_` |
| `capability/` | `csf_`, `csp_`, `chf_`, `cbf_` | `svc_`, `mdw_`, `hal_`, `bsp_` |

The first seven replacements are one-to-one. The four capability
classifications are not: a former `svc_`, `mdw_`, `hal_`, or `bsp_` artifact
becomes `csf_`, `csp_`, `chf_`, or `cbf_` only when it is a genuinely shared or
hardware facility; otherwise it is the feature's own `rmp_` or `efx_`.

## Laws a new Cell follows

- A dependency the Cell may replace (board, chip, medium, transport, OS
  backend) leaves the Cell as porting: a required operation declared in its
  own contract, in its own vocabulary and under its own prefix, bound when the
  Cell is built. Several consumers can then share one provider.
- A library the Cell adopts as-is is imported once by its contract and used
  directly. Core, `smo_` included, uses its representation and calls its pure
  algebra through that import. An adopted operation with an external effect
  stays behind a required operation or in `efx_`. A Cell-local mirror type or
  translation copy of the imported representation is a finding: it adds size
  and link symbols without meaning.
- A run-time callable descriptor, such as a function-pointer table, exists
  only where the provider varies while the Cell runs. Build-time selection
  uses the build system's source sets; weak symbols are not a binding
  mechanism.
- No pass-through wrappers, aliases, shims, dual paths, or function-like or
  identifier-renaming macros.

## Boundary

Template synchronization carries the complete common authoring model, never a
partial vocabulary rewrite. Product-level layering rules belong to the template or fork that owns
that product domain, not to this vendor-neutral scaffold.
