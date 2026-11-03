# Build Optimization

This is the common policy for the speed of the C build tools of the template
maintainer package (`20_ops/tools/comsect1_maint/`: `host_build`,
`cross_build`, `object_cache`). It never trades a build result for speed: a
faster build gives the same bytes as a slower one. Design and measurements:
`20_ops/03_blueprints/shared-maintainer-tools/DESIGN_DIRECTIVE.md` section 15.

## 1. Measure first

Before changing build logic or flags for speed, profile one slow build and
name where the time goes: compiler invocations and their mean time, the same
source compiled more than once (inside one run and across the Cells of a
sequence of runs), helper tools (`nm`, `size`, `objdump`, `ar`), probes,
fixture libraries, record and digest work, version-control checks and Python
overhead. Record the profile with the change. A change without a measured
cause is not an optimization.

## 2. Object cache

- One content-addressed object cache per repository, at the development
  cache `90_temps/development/build/c_objects/` (the one `<tool>/<scope>` of
  the C build tools under `development-feedback-and-release-evidence.md`). It
  is shared by `build.py` and `cross_build.py`, by every Cell and by every run.
  A product's language instructions name it with these commands.
- Key: SHA-256 over the toolchain identity (driver path, `-dumpfullversion`,
  `-dumpmachine`, and the SHA-256 of the driver, `cc1` and `as`), the full
  argument vector with the output path replaced, the compiler environment
  variables that change an object, the target label, the source bytes, and the
  bytes of every file of the compile's gcc `-MD` dependency closure (system
  headers included) together with the entry listing of every directory that
  holds one or is an include root.
- A command holding a relative path is not cached. A failed compile is never
  stored. An entry is verified (SHA-256 of the object) on every read; a
  mismatch is a miss and is repaired by the next compile.
- Writes are atomic (unique temporary name, `os.replace`); concurrent writers
  in threads and processes are safe; a refused replace leaves the entry absent.
- A hit copies the object. `nm` and `size` listings of an object are cached by
  the tool's digest, its arguments and the object's digest.
- Pruning: `python -I -B 20_ops/tools/build.py --prune-object-cache` evicts
  entries unused for 14 days, then the least recently used until the objects
  fit 2 GiB (`--max-age-days`, `--max-bytes`), through one new
  `99_trash/<cleanup-id>/` child. Remove the whole cache with the ordinary
  quarantine of `temporary-output-and-cleanup.md`.
- A release candidate never reuses the development cache: its builds pass
  `--no-object-cache` (`object_cache_mode="run"`), which reuses objects inside
  that one run only. A product's packaging tool does this itself.
- A product hook that observes real compiles (`run_command`) is never served
  from the cache.

## 3. Build once per run

A unit that several Cells of one run compile (a dependency Cell, a shared
binding library, the same unit for another consumer on the same core) is
compiled once and reused within the run, with or without the development
cache. `build.py --cell a --cell b` (or `--all`) builds a library that several
named Cells share (`library_plan`) once.

## 4. Parallel compilation

Compiles, ABI probes, fixture units and per-object listings run on a bounded
worker pool: `--jobs N`, default the logical processors. Object, link and
archive order and every record keep the sequential registry order, so the
output does not depend on the worker count or on completion order.

## 5. Determinism

A cached and a cold build, and a build with any `--jobs`, give byte-identical
objects, libraries, fixture libraries, archives and image build records. Run
records (`build_record.json`, `summary.json`) differ only in run-bound members
(`run_id`, `object_cache` counts, response-file records). Every link is
reproducible (no PE time stamp, a fixed image base); a non-deterministic
output is a defect, not a cache miss to tolerate.

## 6. Flags

- Host: `-O2` semantics stay; units carry `-ffunction-sections
  -fdata-sections -fno-ident` and the product library link `--gc-sections`.
- Cortex-M: size optimization (`-Os`) with function and data sections is the
  measured baseline; a change is admitted only with a measured size and time
  table showing every owner-facing budget unchanged or better.
- Never add a flag that changes semantics (`-ffast-math`, `-fno-strict-*`
  relaxations, `-O3` or other vectorization changes) without a measurement and
  an owner-reviewed record. A flag change is recorded in the design directive
  and in the product's language instructions.

## 7. Verification of a build-speed change

The template tests (`comsect1_maint/test/test_object_cache.py`) cover hit and
miss, header, shadowing-header, compiler, argument, environment and source
invalidation, corrupt entries, concurrent writers, byte identity cold against
warm down to the archive, and pruning. A product adopting a change runs its
tool tests and full Cell builds and tests, and compares the output digests of
a cold and a warm build and of the build before the change.
