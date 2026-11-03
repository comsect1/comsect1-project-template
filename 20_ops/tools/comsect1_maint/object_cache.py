# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Content-addressed object cache of the C build tools (Python standard library only).

One cache serves `host_build` and `cross_build`, across Cells and runs, at the one
named development cache `90_temps/development/build/c_objects/` of the repository
(`DEVELOPMENT_ROOT`). A build that must not reuse a development cache (a release
candidate) uses `ObjectCache(None)`: the same lookup over an in-memory store that
lives for one tool process, so a unit compiled twice in one run is compiled once.

Key of a compiled object, two levels (no preprocessor run before a hit):

- manifest key: SHA-256 over the schema, the target label, the toolchain identity
  (`toolchain_identity`: driver path, `-dumpfullversion`, `-dumpmachine`, and the
  SHA-256 of the driver, `cc1` and `as`), the full argument vector with the output
  path replaced by `<object>`, the compiler environment variables of
  `KEY_ENVIRONMENT`, and the source bytes;
- object key: the manifest key plus the dependency record of one compile: every
  file of gcc's `-MD` dependency closure (system headers included) with its
  SHA-256, and the sorted entry names of every directory that holds such a file
  or is an include root (a header added earlier on the search path is a miss).

A manifest keeps the newest `MANIFEST_RECORDS` dependency records. A lookup
re-hashes the current files of each record; only a record whose every digest
and directory listing still matches yields the object key. The object bytes
are stored once by their own SHA-256 (`blobs/`) and verified on every read; a
mismatch counts as `corrupt` and the unit is compiled again (fail safe: the
cache never decides a build result, it only skips a compile whose inputs are
byte-identical). A command that holds a relative path is never cached.

Tool output over an object (`nm`, `size`) is cached by the tool's own digest,
its argument vector and the object's SHA-256 (`tool_output`).

Concurrency: every file is written to a unique temporary name in its final
directory and published by `os.replace` (atomic on one volume); readers see
the old or the new file, never a part. A replace that the platform refuses
(a reader holds the file) is retried and then abandoned: the cache is only
missing that entry. In one process, a unit being compiled by one worker is
awaited by another worker with the same manifest key.

Pruning (`prune`): entries unused for `max_age_days` (an entry's modification
time is its last use: a hit touches it) are evicted, then the least recently
used until the blobs fit `max_bytes`; blobs, manifests and tool outputs no
entry needs go with them. Evicted files move to one new `99_trash/<cleanup-id>/`
child, which is verified and then deleted. Removing the whole cache uses the
ordinary run quarantine. The cache is operational output, never evidence.
"""

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import uuid

from . import process

SCHEMA = "comsect1.object_cache.v1"
DEVELOPMENT_PARTS = ("90_temps", "development", "build", "c_objects")
# gcc reads these; any of them can change an object.
KEY_ENVIRONMENT = ("CPATH", "C_INCLUDE_PATH", "GCC_EXEC_PREFIX", "COMPILER_PATH", "SOURCE_DATE_EPOCH",
                   "GCC_COMPARE_DEBUG", "DEPENDENCIES_OUTPUT", "SUNPRO_DEPENDENCIES", "LIBRARY_PATH")
MANIFEST_RECORDS = 8
DEFAULT_MAX_AGE_DAYS = 14
DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024
REPLACE_ATTEMPTS = 6
OBJECT_PLACEHOLDER = "<object>"
PATH_FLAGS = ("-I", "-isystem", "-iquote", "-idirafter", "-include", "-imacros")


class CacheError(Exception):
    """The cache location is refused (a link, outside the repository); the message is the reason."""


def development_root(repo_root):
    return os.path.join(repo_root, *DEVELOPMENT_PARTS)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- file digests (per process)

_FILE_DIGESTS = {}
_LISTINGS = {}
_DIGEST_LOCK = threading.Lock()


def file_digest(path):
    """SHA-256 of a file, memoized per process by (size, mtime_ns); None for a file that is absent."""
    key = os.path.normcase(os.path.abspath(path))
    try:
        info = os.stat(key)
    except OSError:
        return None
    stamp = (info.st_size, info.st_mtime_ns)
    with _DIGEST_LOCK:
        known = _FILE_DIGESTS.get(key)
    if known is not None and known[0] == stamp:
        return known[1]
    try:
        digest = process.sha256_file(key)
    except OSError:
        return None
    with _DIGEST_LOCK:
        _FILE_DIGESTS[key] = (stamp, digest)
    return digest


def listing_digest(directory):
    """SHA-256 of the sorted entry names of a directory (None when absent), memoized by its mtime."""
    key = os.path.normcase(os.path.abspath(directory))
    try:
        stamp = os.stat(key).st_mtime_ns
        with _DIGEST_LOCK:
            known = _LISTINGS.get(key)
        if known is not None and known[0] == stamp:
            return known[1]
        digest = _digest(sorted(os.listdir(key)))
    except OSError:
        return None
    with _DIGEST_LOCK:
        _LISTINGS[key] = (stamp, digest)
    return digest


# ---------------------------------------------------------------- toolchain identity

_IDENTITIES = {}


def _query(compiler, argument, env):
    done = subprocess.run([compiler, argument], env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=60, creationflags=process.window_flags())
    if done.returncode != 0:
        raise CacheError("%s %s failed: %s" % (compiler, argument, done.stderr.strip()))
    return done.stdout.strip()


def toolchain_identity(compiler, env=None):
    """The identity of a gcc driver: its path, version, machine and the SHA-256 of the driver, cc1 and as
    (memoized per process by the driver's size and time stamp). `digest` keys the cache."""
    path = os.path.normcase(os.path.abspath(compiler))
    info = os.stat(path)
    memo = (path, info.st_size, info.st_mtime_ns)
    with _DIGEST_LOCK:
        known = _IDENTITIES.get(memo)
    if known is not None:
        return known
    identity = {"path": path, "version": _query(compiler, "-dumpfullversion", env),
                "machine": _query(compiler, "-dumpmachine", env), "files": {}}
    programs = {"driver": compiler}
    for program in ("cc1", "as"):
        located = _query(compiler, "-print-prog-name=%s" % program, env)
        programs[program] = located if os.path.isabs(located) else shutil.which(located, path=(env or os.environ).get("PATH"))
    for name, program in sorted(programs.items()):
        if not program or not os.path.isfile(program):
            raise CacheError("the %s of %s is not found: %s" % (name, compiler, program))
        identity["files"][name] = process.sha256_file(program)
    identity["digest"] = _digest({k: identity[k] for k in ("path", "version", "machine", "files")})
    with _DIGEST_LOCK:
        _IDENTITIES[memo] = identity
    return identity


def tool_identity(tool):
    """Path and SHA-256 of a binutils program (nm, size), for keying its output."""
    path = os.path.normcase(os.path.abspath(tool))
    return {"path": path, "sha256": file_digest(path)}


# ---------------------------------------------------------------- dependency files

def parse_depfile(text):
    """The prerequisites of gcc's `-MD` output (one rule): unescapes `\\ `, `\\#` and `$$`, joins
    continuation lines and drops the target. Windows path backslashes stay literal."""
    joined = text.replace("\\\r\n", " ").replace("\\\n", " ")
    tokens, current, index = [], [], 0
    while index < len(joined):
        char = joined[index]
        following = joined[index + 1] if index + 1 < len(joined) else ""
        if char == "\\" and following in (" ", "#"):
            current.append(following)
            index += 2
            continue
        if char == "$" and following == "$":
            current.append("$")
            index += 2
            continue
        if char in " \t\r\n":
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
        index += 1
    if current:
        tokens.append("".join(current))
    for position, token in enumerate(tokens):
        if token.endswith(":"):
            return tokens[position + 1:]
        if token == ":":
            return tokens[position + 1:]
    raise ValueError("no rule in the dependency file")


def path_arguments(command, flags=PATH_FLAGS):
    """[(flag, path)] of every path option of `command`, in the separate (`-I dir`) and the joined
    (`-Idir`) spelling; a flag without its value yields (flag, None)."""
    found = []
    for index, argument in enumerate(command):
        for flag in flags:
            if argument == flag:
                found.append((flag, command[index + 1] if index + 1 < len(command) else None))
                break
            if argument.startswith(flag):
                found.append((flag, argument[len(flag):]))
                break
    return found


def command_paths_absolute(command, source):
    """True when the source and every path option of `command` are absolute (the key omits the cwd)."""
    return os.path.isabs(source) and all(path is not None and os.path.isabs(path)
                                         for _flag, path in path_arguments(command))


def include_roots(command):
    """The search directories of `command` (-I, -isystem, -iquote, -idirafter), in order."""
    return [path for _flag, path in path_arguments(command, PATH_FLAGS[:4]) if path is not None]


# ---------------------------------------------------------------- stores

class _MemoryStore:
    """One process's store: reuse inside one run, nothing persists."""

    persistent = False

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def read(self, kind, key):
        with self._lock:
            return self._data.get((kind, key))

    def write(self, kind, key, data):
        with self._lock:
            self._data[(kind, key)] = data

    def touch(self, kind, key):
        pass


class _DiskStore:
    """The development cache folder: `<kind>/<key[:2]>/<key><suffix>`, atomic publication."""

    persistent = True
    SUFFIX = {"manifests": ".json", "entries": ".json", "blobs": ".o", "outputs": ".json"}

    def __init__(self, root, repo_root):
        try:
            self.root = process.checked_path(root, repo_root)
        except RuntimeError as error:
            raise CacheError(str(error))
        os.makedirs(self.root, exist_ok=True)
        try:
            process.checked_path(self.root, repo_root)
        except RuntimeError as error:
            raise CacheError(str(error))
        marker = os.path.join(self.root, "cache.json")
        if not os.path.isfile(marker):
            self._publish(marker, (json.dumps({"schema": SCHEMA}) + "\n").encode("utf-8"))
        schema = None
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                with open(marker, "r", encoding="utf-8") as handle:
                    schema = json.load(handle).get("schema")
                break
            except (OSError, ValueError, AttributeError):
                time.sleep(0.01 * (attempt + 1))  # another writer is publishing the marker
        if schema != SCHEMA:
            raise CacheError("%s is not a %s cache (remove it through 99_trash)" % (self.root, SCHEMA))

    def path(self, kind, key):
        return os.path.join(self.root, kind, key[:2], key + self.SUFFIX[kind])

    def read(self, kind, key):
        try:
            with open(self.path(kind, key), "rb") as handle:
                return handle.read()
        except OSError:
            return None

    def write(self, kind, key, data):
        target = self.path(kind, key)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        self._publish(target, data)

    def touch(self, kind, key):
        try:
            os.utime(self.path(kind, key))
        except OSError:
            pass

    @staticmethod
    def _publish(target, data):
        temporary = "%s.%d.%s.tmp" % (target, os.getpid(), uuid.uuid4().hex)
        with open(temporary, "xb") as handle:
            handle.write(data)
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, target)
                return True
            except PermissionError:
                time.sleep(0.01 * (attempt + 1))
        try:
            os.remove(temporary)
        except OSError:
            pass
        return False


# ---------------------------------------------------------------- the cache

class ObjectCache:
    """`ObjectCache(root, repo_root)` uses the development cache at `root`; `ObjectCache(None)` reuses
    objects inside one process only. Thread-safe; `statistics()` counts hits, misses, stores, corrupt
    entries and uncached compiles."""

    def __init__(self, root, repo_root=None):
        self.store = _MemoryStore() if root is None else _DiskStore(root, repo_root or process.REPO_ROOT)
        self.root = None if root is None else self.store.root
        self._lock = threading.Lock()
        self._unit_locks = {}
        self.counts = {"hits": 0, "misses": 0, "stores": 0, "corrupt": 0, "uncached": 0,
                       "tool_hits": 0, "tool_runs": 0}

    def _count(self, name):
        with self._lock:
            self.counts[name] += 1

    def statistics(self, repo_root=None):
        mode = "development" if self.store.persistent else "run"
        root = None
        if self.root is not None:
            root = os.path.relpath(self.root, repo_root).replace("\\", "/") if repo_root else self.root
        with self._lock:
            return dict(self.counts, mode=mode, root=root)

    def _unit_lock(self, key):
        with self._lock:
            return self._unit_locks.setdefault(key, threading.Lock())

    def _json(self, kind, key):
        data = self.store.read(kind, key)
        if data is None:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._count("corrupt")
            return None

    def _blob(self, digest):
        data = self.store.read("blobs", digest)
        if data is None:
            return None
        if hashlib.sha256(data).hexdigest() != digest:
            self._count("corrupt")
            return None
        return data

    # -- compile

    def manifest_key(self, identity, command, output, source, env, target):
        source_digest = file_digest(source)
        if source_digest is None:
            return None
        argv = [OBJECT_PLACEHOLDER if argument == output else argument for argument in command]
        environment = {name: (env or {}).get(name) for name in KEY_ENVIRONMENT}
        return _digest({"schema": SCHEMA, "target": target, "toolchain": identity["digest"], "argv": argv,
                        "environment": environment, "source": source_digest})

    @staticmethod
    def _object_key(manifest, record):
        return _digest({"manifest": manifest, "files": record["files"], "directories": record["directories"]})

    @staticmethod
    def _record_matches(record):
        for path, digest in record["files"]:
            if file_digest(path) != digest:
                return False
        for directory, digest in record["directories"]:
            if listing_digest(directory) != digest:
                return False
        return True

    def _lookup(self, manifest):
        records = self._json("manifests", manifest)
        if not isinstance(records, dict) or records.get("schema") != SCHEMA:
            return None
        for record in records.get("records", []):
            if not self._record_matches(record):
                continue
            key = self._object_key(manifest, record)
            entry = self._json("entries", key)
            if not isinstance(entry, dict) or not isinstance(entry.get("object_sha256"), str):
                continue
            data = self._blob(entry["object_sha256"])
            if data is None:
                continue
            self.store.touch("entries", key)
            self.store.touch("manifests", manifest)
            return data
        return None

    def _record(self, depfile, source, command):
        """The dependency record of one compile, or None when the dependency file is not usable."""
        try:
            with open(depfile, "r", encoding="utf-8", errors="strict") as handle:
                names = parse_depfile(handle.read())
        except (OSError, ValueError, UnicodeDecodeError):
            return None
        files = {}
        for name in names:
            path = os.path.normcase(os.path.abspath(name))
            digest = file_digest(path)
            if digest is None:
                return None
            files[path] = digest
        if os.path.normcase(os.path.abspath(source)) not in files:
            return None
        directories = {os.path.dirname(path) for path in files}
        directories.update(os.path.normcase(os.path.abspath(root)) for root in include_roots(command))
        listed = []
        for directory in sorted(directories):
            listed.append([directory, listing_digest(directory)])
        return {"files": sorted([path, digest] for path, digest in files.items()), "directories": listed}

    def compile(self, command, output, source, env, run, scratch_dir, identity, target):
        """Produce `output` from `command` (a gcc argument vector with `-c`, `-o output`): copy a verified
        cached object, or run `run(command + dependency flags)` and store the result. Returns True on a hit.
        `run` raises on a failed compile (a failure is never cached)."""
        manifest = None
        if command_paths_absolute(command, source) and output in command:
            manifest = self.manifest_key(identity, command, output, source, env, target)
        if manifest is None:
            self._count("uncached")
            run(command)
            return False
        with self._unit_lock(manifest):
            data = self._lookup(manifest)
            if data is not None:
                with open(output, "wb") as handle:
                    handle.write(data)
                self._count("hits")
                return True
            self._count("misses")
            depfile = os.path.join(scratch_dir, "dep_%s.d" % manifest[:24])
            run(command + ["-MD", "-MF", depfile])
            record = self._record(depfile, source, command)
            if record is None:
                return False
            with open(output, "rb") as handle:
                data = handle.read()
            digest = hashlib.sha256(data).hexdigest()
            stored = self.store.read("blobs", digest)
            if stored is None or hashlib.sha256(stored).hexdigest() != digest:
                self.store.write("blobs", digest, data)
            key = self._object_key(manifest, record)
            self.store.write("entries", key, json.dumps({"schema": SCHEMA, "object_sha256": digest,
                                                         "size": len(data)}).encode("utf-8"))
            records = self._json("manifests", manifest)
            kept = records.get("records", []) if isinstance(records, dict) else []
            kept = [record] + [old for old in kept if old != record]
            self.store.write("manifests", manifest, json.dumps({"schema": SCHEMA,
                                                                "records": kept[:MANIFEST_RECORDS]}).encode("utf-8"))
            self._count("stores")
            return False

    # -- tool output over an object

    def tool_output(self, command, object_path, run):
        """stdout of `command` (nm or size over `object_path`): cached by the tool digest, the argument
        vector and the object's SHA-256; the object path in the text is restored on a hit."""
        tool = tool_identity(command[0])
        digest = file_digest(object_path)
        if tool["sha256"] is None or digest is None:
            self._count("tool_runs")
            return run(command)
        argv = [OBJECT_PLACEHOLDER if argument == object_path else argument for argument in command]
        key = _digest({"schema": SCHEMA, "tool": tool, "argv": argv, "object": digest})
        entry = self._json("outputs", key)
        if isinstance(entry, dict) and isinstance(entry.get("stdout"), str) \
                and hashlib.sha256(entry["stdout"].encode("utf-8")).hexdigest() == entry.get("stdout_sha256"):
            self.store.touch("outputs", key)
            self._count("tool_hits")
            return entry["stdout"].replace(OBJECT_PLACEHOLDER, object_path)
        stdout = run(command)
        self._count("tool_runs")
        stored = stdout.replace(object_path, OBJECT_PLACEHOLDER)
        self.store.write("outputs", key, json.dumps({"schema": SCHEMA, "stdout": stored,
                                                     "stdout_sha256": hashlib.sha256(stored.encode("utf-8")).hexdigest()}
                                                    ).encode("utf-8"))
        return stdout


# ---------------------------------------------------------------- pruning

def prune(root, repo_root, max_age_days=DEFAULT_MAX_AGE_DAYS, max_bytes=DEFAULT_MAX_BYTES, now=None,
          announce=None):
    """Evict unused entries of the development cache at `root` (module documentation); returns the counts."""
    try:
        root = process.checked_path(root, repo_root)
    except RuntimeError as error:
        raise CacheError(str(error))
    result = {"entries": 0, "evicted_entries": 0, "evicted_files": 0, "evicted_bytes": 0, "kept_bytes": 0}
    if not os.path.isdir(root):
        return result
    now = time.time() if now is None else now
    limit = now - max_age_days * 86400

    def files(kind):
        found = []
        base = os.path.join(root, kind)
        for directory, names, children in os.walk(base):
            names.sort()
            for name in sorted(children):
                path = os.path.join(directory, name)
                if process.is_link(path):
                    raise CacheError("refusing a link in the cache: %s" % path)
                if not name.endswith(".tmp"):
                    found.append(path)
        return found

    entries = []
    for path in files("entries"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                blob = json.load(handle).get("object_sha256")
        except (OSError, ValueError):
            blob = None
        entries.append((os.stat(path).st_mtime, path, blob))
    result["entries"] = len(entries)
    blobs = {os.path.basename(path)[:-2]: path for path in files("blobs")}
    sizes = {digest: os.stat(path).st_size for digest, path in blobs.items()}
    entries.sort()
    evict = [entry for entry in entries if entry[0] < limit or entry[2] not in blobs]
    evicted = set(entry[1] for entry in evict)
    kept = [entry for entry in entries if entry[1] not in evicted]
    references = {}
    for entry in kept:
        references[entry[2]] = references.get(entry[2], 0) + 1
    total = sum(sizes[digest] for digest in references)
    while kept and total > max_bytes:
        oldest = kept.pop(0)
        evict.append(oldest)
        references[oldest[2]] -= 1
        if references[oldest[2]] == 0:
            del references[oldest[2]]
            total -= sizes[oldest[2]]
    used = set(references)
    victims = [entry[1] for entry in evict]
    victims += [path for digest, path in blobs.items() if digest not in used]
    for kind in ("manifests", "outputs"):
        victims += [path for path in files(kind) if os.stat(path).st_mtime < limit]
    result["evicted_entries"] = len(evict)
    result["kept_bytes"] = total
    if not victims:
        return result
    cleanup = "object_cache_prune-%s" % process.new_run_id("evict")
    trash = process.checked_path(os.path.join(repo_root, "99_trash", cleanup), repo_root)
    if os.path.lexists(trash):
        raise CacheError("quarantine child exists: %s" % trash)
    moved = []
    for path in victims:
        relative = os.path.relpath(path, root)
        target = os.path.join(trash, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        size = os.stat(path).st_size
        try:
            os.replace(path, target)
        except OSError:
            continue  # in use by a reader: it stays, and goes in a later prune
        moved.append((target, size))
    if announce is not None:
        announce("object cache prune: %d files to %s" % (len(moved), trash))
    process.checked_path(trash, repo_root)
    if any(not os.path.isfile(target) for target, _ in moved):
        raise CacheError("quarantine of evicted cache files failed verification: %s" % trash)
    shutil.rmtree(trash)
    result["evicted_files"] = len(moved)
    result["evicted_bytes"] = sum(size for _, size in moved)
    return result
