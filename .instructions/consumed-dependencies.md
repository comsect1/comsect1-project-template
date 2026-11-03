# Consumed Dependencies

This is the common policy for how a repository consumes an SDK, a RUNTIME, a
library, a tool or a checkout that another repository issues (the Foundation
checkout of `host_build.standard_pin`, an adopted `external_headers` tree, an
installed SDK, the Gate set and its toolchain). Owner decision 2026-11-03.

## 1. No consumer locks

A consumer never re-verifies the executables or libraries it consumes and
never locks their version. The build, test and run tools of a consumer do not
refuse on:

- an exact commit pin, or a pinned checkout that is not clean at that commit;
- an exact version or an upper version bound;
- a content digest that differs from a recorded one.

## 2. Allowed

- A minimum version (floor), `"minimum_version": "<semver>"`, where the
  dependency has a version notion and a real minimum exists.
- Interface negotiation: the C ABI identity and layout, Provider negotiate,
  the MCP protocol revision.
- Structural resolution: the dependency is found, lies outside the consumer
  repository, and holds the file the consumer includes or loads. Nothing can
  be compiled or run otherwise.

## 3. Pins and digests are metadata

A pin file (`10_pkg/components/*.json`) names where a dependency comes from
and the commit it was last pinned at. A content digest covers the inside of a
deliverable only, excluding its root folder name. Both are read and recorded
for debugging, never a condition. The C build tools resolve the Foundation
root from the pin's `root_variable` (override) or its optional absolute
`local_root`, and record `fnd_sdk_standard` (root, source, `pinned_commit`,
observed `head`, `dirty`, `matches_pin`) in `build_record.json` and the
cross-build `summary.json`; an `external_headers` checkout is recorded the same
way per result. The native Gate records the actual Gate binary digests beside
the recorded `expected_sha256` (`tool_sha256_differs`) and the toolchain
manifest, member and semantic runtime digests with every difference
(`native_toolchain`).

The object cache keys a compile by the bytes of the headers actually read
([build optimization](./build-optimization.md)), so build correctness never
rests on a pin.

## 4. Where verification stays

Verification of content belongs to the issuing side and the install step, not
to a consumer's build or run:

- install time: `install-sdk --expect-tag-sha256`;
- issue time: a product's own `package.py --issue` reproducibility and
  release checks over its own deliverable.

A repository's own synchronized common layer (`sync.py --check`, the
maintainer tools drift check) is the repository's own content, not a consumed
dependency.
