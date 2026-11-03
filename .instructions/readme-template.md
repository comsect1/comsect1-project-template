# README Template

The root `README.md` of a product repository is an external introduction. It
tells a reader who does not know the Comsect1 Platform what the product is,
where it sits, what it ships and under which terms. It is not the maintainer's
entry point: that is `AGENTS.md` and the instruction indexes.

Every product README follows the structure below, with these headings in this
order. Keep the whole file to roughly one screen.

## Structure

1. **Title:** `# <Product Name> (<ABBR>)`, the exact product name and its
   abbreviation as the canon and the repository glossary spell them. No history
   or version label (`reboot`, `legacy`, `v2`, `r{n}`) anywhere in the file.
2. **Overview** (no heading, one paragraph under the title): what the product
   is and what problem it solves.
3. `## Place in the Comsect1 Platform`: the tier and the role, in one or two
   sentences, as the Master Architecture Canon classifies the product.
4. `## What it is not`: the product is domain-blind. Name what comes from
   outside it (Providers, authored assets, the consumer) and state that it
   knows no domain package.
5. `## Deliverables`: the deliverable axes the repository issues (`RUNTIME`,
   `SDK`, `PACKAGE`, `APPLICATION`) per target, at a high level; one line per
   axis and target. No file inventories.
6. `## Getting started`: install the SDK on a developer PC with the common SDK
   tool it carries (`python -I <sdk_root>/tools/comsect1_sdk.pyz install-sdk
   --source <sdk_root>`; `comsect1_sdk.pyz sync-installs --workspace <dir>`
   installs every issued deliverable below `<dir>` that is not current) and
   point to the SDK guide in `10_pkg/doc/`, which documents `install-sdk`,
   `locate` and `sync-installs` with the version-keyed installed layout.
7. `## Documentation`: links to the external-facing documents only: the SDK
   and deliverable guides in `10_pkg/doc/` and the glossary. Do not link
   `AGENTS.md`, `.instructions/` or a blueprint that holds machine-local
   paths, commit hashes or decision history.
8. `## License`: the SPDX identifier, a pointer to `LICENSE.md` and
   `NOTICE.md`, whether released packages carry third-party notices, and the
   copyright line `Copyright 2026 Kim Hyeongjeong (comsect1)`: the Apache-2.0
   appendix form of `LICENSE.md`, which `NOTICE.md` repeats verbatim (never
   "All rights reserved", which contradicts the Apache grant).
9. `## Status`: the current version from `20_ops/version.json`, and that the
   product is pre-1.0 while that is the case.

## Rules

- Every claim comes from the repository's own documents or code. Do not
  describe a capability the repository does not implement or document.
- No internal content: no session or work history, no absolute or
  machine-local paths, no agent or assistant process notes, no commit hashes,
  no owner decision records. Move such content to `.instructions/local/` or
  `20_ops/` and link it from `## Documentation` only when an external reader
  needs it.
- Relative links only, to files that exist in the repository.
- The product name, the license statement, the copyright line and the version
  must agree with the canon, the glossary, `LICENSE.md`, `NOTICE.md` and
  `20_ops/version.json`.
- `README.md` is authored text: it follows the text-format policy and is
  checked by `python -I -B 20_ops/tools/text_format.py`.

This file is a common instruction. Template synchronization may update it; a
repository that needs a different README structure records the deviation in
`.instructions/local/` instead of editing this file.
