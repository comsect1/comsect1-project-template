# Development Feedback and Release Evidence

## Purpose

Development feedback and release evidence have different purposes and must not
be conflated. Fast feedback keeps implementation moving. Release evidence
establishes that a candidate may be distributed. A command suitable for one is
not automatically suitable for the other.

## Development feedback

During ordinary implementation, run only the quickest language- and
change-appropriate feedback operation. It may reuse one explicitly named
disposable cache below `90_temps/development/<tool>/<scope>/`. It must not
claim to be a test result, complete verification result, structural verdict, or
release evidence.

Do not run a complete test suite, clean-room build, full static-analysis pass,
package-production flow, or complete Cell verification for each edit. Those operations
belong to a release candidate unless a governing specification, an identified
external contract, or an authorized work order expressly requires an earlier
check.

The fork's kind or local instructions define the concrete language and tool
operation: its command, affected-unit selection, reusable cache location, and
the cases that require an executable rather than a compiler or syntax check.
They may strengthen this policy for an identified safety or contract boundary,
but may not represent fast feedback as release evidence.

## Release evidence

Only a release candidate runs its complete required test suite, formal
verification, linting or static analysis, package checks, and applicable Cell
structural verification. Its build and verification output uses a newly created, non-overlapping
task-owned run below `90_temps/`; it must not reuse a development cache.

Record the candidate subject, commands, tool identities, inputs, outputs, and
results in the release or verification record that owns the candidate. A
passing development operation does not waive any release-candidate check.

## Cache lifecycle

A reusable development cache is operational output, not retained evidence. It
is permitted only at the exact `90_temps/development/<tool>/<scope>/` location
defined by the fork. Keep it ignored, disposable, and separate from every
task-owned run. Remove it through the ordinary quarantine procedure when the
work scope ends or the cache becomes stale; never promote it to `20_ops/` or
`30_cert/`.
