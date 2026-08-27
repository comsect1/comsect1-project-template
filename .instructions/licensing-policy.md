# Comsect1 Unit Template Licensing Policy

This repository is the upstream licensing-policy SSOT for unit templates. It
describes boundaries; the root [LICENSE.md](../LICENSE.md) is the controlling
license text for the template itself.

## Material boundaries

| Material | License authority |
|---|---|
| Template scaffold, `.instructions/`, and reusable guides | Apache-2.0 with Comsect1 Template Instantiation Exception |
| Material authored in a downstream `10_pkg/` | License selected and declared by that downstream owner |
| Reviewed records in `20_ops/` and issued packages in `30_cert/` | Owning project's declared terms and applicable evidence controls |
| Generated output in `90_temps/` | Determined by its inputs and generators; generation does not erase upstream terms |
| Third-party or vendored material | Original license and notices, unchanged |

The instantiation exception separates downstream authored work from the
template scaffold. It does not grant permission to relicense copied Comsect1 or
third-party material.

## Adoption requirements

1. Preserve the Comsect1 `LICENSE.md` and `NOTICE.md` for retained template
   material and record the exact upstream baseline.
2. Declare the downstream owner's license before authored implementation is
   added. Public and proprietary projects may choose different terms.
3. Mark authored source with accurate SPDX copyright and license identifiers.
4. Preserve all inbound license headers and required notices.
5. Inventory direct, transitive, vendored, generated, and bundled material
   before release; review compatibility for the actual linking and distribution
   model instead of inferring permission from repository placement.
6. Include required licenses, notices, and an SBOM in released packages.

`comsect1.json` may declare a Cell's non-derivable license identity, but it
cannot override the controlling license text or third-party terms.
