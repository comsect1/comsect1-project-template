# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Native C Gate lane driver for Comsect1 Cells (Python standard library only).

Usage:
    python -I -B 20_ops/tools/native_gate.py --cell <cell-root> \
        --config <lane-config.json> [--lane native|plain|both] [--run-id ID] \
        [--accept-tool-hashes] [--accept-tool-drift]

The Cell is read only. All output goes to
`90_temps/verification/native_gate/<run-id>/` of this repository. The tool
makes no network access; it only starts the installed Gate set binaries and
clang (header closure and resource directory). Every process runs without a
window, with stdin closed, under a timeout, and its whole process tree is
killed on timeout. Text is decoded as UTF-8 explicitly everywhere. Every path
the plan reads is checked component by component before canonicalization:
a linked or reparse component is refused.

The lane configuration selects the clang resource in one of two shapes:
`{"manifest", "manifest_sha256"}` admits one pinned toolchain inventory (the
manifest's every member is hashed, locked for the run and the closure may only
read admitted resource headers); `{"resource_dir", "required_major",
"clang_candidates"}` discovers clang and checks its resource directory.
`publications` (optional) selects the input owner protocol: when the member is
present (even `[]`), each `comsect1-native-input` call names the original
source Cells of its external inputs (`--source-cell`) and the selected SDK
publication roots (`--publication`), which needs a native-input that accepts
them; when it is absent, external inputs are passed by id only.

Exit codes (tool codes, not Gate codes; the Gate exit code is recorded in the
summary). With `--lane both` the highest code of the lanes is returned.

     0  PASS                 every selected lane has verdict PASS
     1  FAIL                 a lane has Gate verdict FAIL
     2  USAGE                invalid command line
     3  INDETERMINATE        a lane has Gate verdict INDETERMINATE (blocked)
     4  CONFIG               lane configuration unreadable or invalid, or maintainer tools drift
     5  TOOL_SET_UNAVAILABLE installed Gate set or a binary is absent
     6  TOOL_HASH_MISMATCH   binary hash differs from the configuration
     7  CLANG_UNAVAILABLE    clang or its resource directory not usable
     8  CELL_INVALID         Cell root missing, not a Cell, link, or no C unit
     9  OUTPUT_INVALID       run id or output directory refused
    10  PLAN_FAILED          header closure or native plan could not be built
    11  NATIVE_INPUT_FAILED  comsect1-native-input failed
    12  GATE_REFUSED         Gate wrote no usable report or contradicted itself
    13  TIMEOUT              a process exceeded its timeout and was killed
    14  INTERNAL             unexpected tool error
"""

import argparse
from contextlib import ExitStack, contextmanager
import ctypes
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import config as maint_config
from . import path_guard as _path_guard
from . import process
from .process import is_link, sha256_file, sha256_text, write_text, write_json

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_INDETERMINATE = 3
EXIT_CONFIG = 4
EXIT_TOOL_SET_UNAVAILABLE = 5
EXIT_TOOL_HASH_MISMATCH = 6
EXIT_CLANG_UNAVAILABLE = 7
EXIT_CELL_INVALID = 8
EXIT_OUTPUT_INVALID = 9
EXIT_PLAN_FAILED = 10
EXIT_NATIVE_INPUT_FAILED = 11
EXIT_GATE_REFUSED = 12
EXIT_TIMEOUT = 13
EXIT_INTERNAL = 14

EXIT_NAMES = {
    0: "PASS", 1: "FAIL", 2: "USAGE", 3: "INDETERMINATE", 4: "CONFIG",
    5: "TOOL_SET_UNAVAILABLE", 6: "TOOL_HASH_MISMATCH", 7: "CLANG_UNAVAILABLE",
    8: "CELL_INVALID", 9: "OUTPUT_INVALID", 10: "PLAN_FAILED",
    11: "NATIVE_INPUT_FAILED", 12: "GATE_REFUSED", 13: "TIMEOUT", 14: "INTERNAL",
}

TOOL_KEYS = ("gate", "native_input", "c_frontend", "libclang")
CONFIG_KEYS = ("gate_set", "expected_sha256", "build", "clang_resource", "timeouts_seconds")
MANIFEST_KEYS = ("manifest", "manifest_sha256")
DISCOVERY_KEYS = ("resource_dir", "required_major", "clang_candidates")
RUN_ID_PATTERN = process.RUN_ID_PATTERN
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
AUTHORITY_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
REPARSE_FLAG = process.REPARSE_FLAG
CREATE_NO_WINDOW = process.CREATE_NO_WINDOW
CREATE_NEW_PROCESS_GROUP = process.CREATE_NEW_PROCESS_GROUP
REPO_ROOT = Path(process.REPO_ROOT)
COUNT_NAMES = ("assessment_count", "debt_count", "limit_count", "notice_count", "rework_count", "violation_count")


class ToolError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def checked_original_path(path):
    try:
        return _path_guard.checked_path(path)
    except (OSError, ValueError) as error:
        raise ToolError(EXIT_PLAN_FAILED, "unsafe original path %s: %s" % (path, error)) from error


def expand(text, what):
    """Expand %NAME% references; an unset or non-absolute variable is an error."""
    missing = []

    def replace(match):
        value = os.environ.get(match.group(1))
        if value is None or not os.path.isabs(value):
            missing.append(match.group(1))
            return match.group(0)
        return value

    result = re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", replace, text)
    if missing:
        raise ToolError(EXIT_CONFIG, "%s uses unset or non-absolute variable %s" % (what, ", ".join(missing)))
    return result


# ---------------------------------------------------------------- configuration

def require(condition, message):
    if not condition:
        raise ToolError(EXIT_CONFIG, message)


def check_keys(section, name, keys):
    require(isinstance(section, dict), "%s must be an object" % name)
    require(set(section) == set(keys), "%s must have exactly the members %s" % (name, ", ".join(sorted(keys))))


def load_config(path):
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
        config = json.loads(raw)
    except (OSError, ValueError) as error:
        raise ToolError(EXIT_CONFIG, "configuration %s unreadable: %s" % (path, error))
    require(isinstance(config, dict), "configuration must be an object")
    check_keys(config, "configuration", CONFIG_KEYS + (("publications",) if "publications" in config else ()))
    gate_set = config["gate_set"]
    check_keys(gate_set, "gate_set", ("runtime_root", "active_set_file", "binary_subdirectory", "binaries"))
    for key in ("runtime_root", "active_set_file", "binary_subdirectory"):
        require(isinstance(gate_set[key], str) and gate_set[key], "gate_set.%s must be a non-empty string" % key)
    check_keys(gate_set["binaries"], "gate_set.binaries", TOOL_KEYS)
    for key in TOOL_KEYS:
        name = gate_set["binaries"][key]
        require(isinstance(name, str) and name and Path(name).name == name, "gate_set.binaries.%s must be a file name" % key)
    check_keys(config["expected_sha256"], "expected_sha256", TOOL_KEYS)
    for key in TOOL_KEYS:
        value = config["expected_sha256"][key]
        require(isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None,
                "expected_sha256.%s must be 64 lowercase hex digits" % key)
    build = config["build"]
    check_keys(build, "build", ("target", "standard", "plain_char", "virtual_root",
                                "preprocessing_epoch_seconds", "definitions", "include_roots",
                                "external_include_roots", "system_include_roots"))
    for key in ("target", "virtual_root"):
        require(isinstance(build[key], str) and build[key], "build.%s must be a non-empty string" % key)
    require(build["standard"] in ("c99", "c11", "c17"), "build.standard must be c99, c11 or c17")
    require(build["plain_char"] in ("signed", "unsigned"), "build.plain_char must be signed or unsigned")
    require(isinstance(build["preprocessing_epoch_seconds"], int) and not isinstance(build["preprocessing_epoch_seconds"], bool)
            and build["preprocessing_epoch_seconds"] >= 0, "build.preprocessing_epoch_seconds must be a non-negative integer")
    definitions = build["definitions"]
    require(isinstance(definitions, dict), "build.definitions must be an object")
    for name, value in definitions.items():
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None, "build.definitions name %r is not an identifier" % name)
        require(isinstance(value, str) and value != "" and "\n" not in value,
                "build.definitions.%s must be a non-empty single-line string (flag-style -DX is \"1\")" % name)
    roots = build["include_roots"]
    require(isinstance(roots, list) and roots, "build.include_roots must be a non-empty list")
    for root in roots:
        require(isinstance(root, str) and root, "build.include_roots entries must be non-empty strings")
        parts = root.replace("\\", "/").split("/")
        require(not os.path.isabs(root) and ".." not in parts and ":" not in root,
                "build.include_roots entry %r must be Cell-relative (\".\" is the Cell root)" % root)
    require(len(set(roots)) == len(roots), "build.include_roots has a duplicate entry")
    external_roots = build["external_include_roots"]
    require(isinstance(external_roots, list), "build.external_include_roots must be a list")
    for root in external_roots:
        require(isinstance(root, str) and root, "build.external_include_roots entries must be non-empty strings")
        parts = root.replace("\\", "/").split("/")
        require(not os.path.isabs(root) and ".." not in parts and ":" not in root and root != ".",
                "build.external_include_roots entry %r must be repository-relative (the membrane of a dependency Cell)" % root)
    require(len(set(external_roots)) == len(external_roots), "build.external_include_roots has a duplicate entry")
    system_roots = build["system_include_roots"]
    require(isinstance(system_roots, list), "build.system_include_roots must be a list")
    for root in system_roots:
        require(isinstance(root, str) and root and os.path.isabs(root) and ".." not in root.replace("\\", "/").split("/"),
                "build.system_include_roots entry %r must be an absolute directory (an external SDK, read only)" % (root,))
    require(len(set(system_roots)) == len(system_roots), "build.system_include_roots has a duplicate entry")
    publications = config.get("publications", [])
    require(isinstance(publications, list), "publications must be a list")
    for publication in publications:
        check_keys(publication, "publication", ("canonical_root", "inventory_member", "declaration_member"))
        require(isinstance(publication["canonical_root"], str) and publication["canonical_root"],
                "publication.canonical_root must explicitly select a root")
        for key in ("inventory_member", "declaration_member"):
            member = publication[key]
            require(isinstance(member, str) and member and "\\" not in member and ":" not in member
                    and all(part not in ("", ".", "..") and not part.endswith((" ", "."))
                            for part in member.split("/")),
                    "publication.%s must be an unaliased relative member" % key)
    clang = config["clang_resource"]
    require(isinstance(clang, dict), "clang_resource must be an object")
    if set(clang) == set(MANIFEST_KEYS):
        require(isinstance(clang["manifest"], str) and clang["manifest"],
                "clang_resource.manifest must explicitly select provenance")
        require(isinstance(clang["manifest_sha256"], str)
                and SHA256_PATTERN.fullmatch(clang["manifest_sha256"]) is not None,
                "clang_resource.manifest_sha256 must pin the provenance bytes")
        config["_clang_mode"] = "manifest"
    elif set(clang) == set(DISCOVERY_KEYS):
        require(clang["resource_dir"] is None or (isinstance(clang["resource_dir"], str) and clang["resource_dir"]),
                "clang_resource.resource_dir must be null or a non-empty string")
        require(isinstance(clang["required_major"], str) and clang["required_major"].isdigit(),
                "clang_resource.required_major must be a digit string")
        cands = clang["clang_candidates"]
        require(isinstance(cands, list) and all(isinstance(c, str) and c for c in cands),
                "clang_resource.clang_candidates must be a list of strings")
        require(clang["resource_dir"] is not None or cands, "clang_resource needs resource_dir or clang_candidates")
        config["_clang_mode"] = "discovery"
    else:
        raise ToolError(EXIT_CONFIG, "clang_resource must have exactly the members %s (pinned manifest) or %s "
                        "(discovery)" % (", ".join(MANIFEST_KEYS), ", ".join(sorted(DISCOVERY_KEYS))))
    timeouts = config["timeouts_seconds"]
    check_keys(timeouts, "timeouts_seconds", ("clang", "native_input", "gate"))
    for key, value in timeouts.items():
        require(isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 3600,
                "timeouts_seconds.%s must be an integer from 1 to 3600" % key)
    config["_sha256"] = sha256_text(raw)
    return config


# ---------------------------------------------------------------- process control

def run_process(name, command, timeout, cwd, log_path=None):
    """Run one process; return (exit code, stdout text, stderr text)."""
    try:
        return process.run_process(name, command, timeout, cwd, log_path)
    except process.ProcessError as error:
        raise ToolError(EXIT_TIMEOUT if error.kind == "timeout" else EXIT_INTERNAL, error.message)


# ---------------------------------------------------------------- tools and clang

def resolve_gate_set(config):
    """Return (bin_dir, {key: Path}, release_set_id) of the active installed set."""
    gate_set = config["gate_set"]
    root = Path(expand(gate_set["runtime_root"], "gate_set.runtime_root"))
    active = root / gate_set["active_set_file"]
    try:
        record = json.loads(active.read_text(encoding="utf-8"))
        set_path = record["set_path"]
        set_id = record["release_set_id"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ToolError(EXIT_TOOL_SET_UNAVAILABLE, "active Gate set record %s unusable: %s" % (active, error))
    if not isinstance(set_path, str) or not isinstance(set_id, str) or os.path.isabs(set_path) \
            or ".." in set_path.replace("\\", "/").split("/"):
        raise ToolError(EXIT_TOOL_SET_UNAVAILABLE, "active Gate set record has an unsafe set_path")
    bin_dir = root / set_path / gate_set["binary_subdirectory"]
    if not bin_dir.is_dir():
        raise ToolError(EXIT_TOOL_SET_UNAVAILABLE, "Gate set binary directory %s is absent" % bin_dir)
    paths = {}
    for key in TOOL_KEYS:
        path = bin_dir / gate_set["binaries"][key]
        if not path.is_file():
            raise ToolError(EXIT_TOOL_SET_UNAVAILABLE, "Gate set binary %s is absent" % path)
        paths[key] = path
    return bin_dir, paths, set_id


def check_tool_hashes(config, paths, accept):
    actual = {key: sha256_file(paths[key]) for key in TOOL_KEYS}
    mismatched = [key for key in TOOL_KEYS if actual[key] != config["expected_sha256"][key]]
    if accept:
        for key in TOOL_KEYS:
            print("tool_hash %s actual=%s expected=%s%s" % (
                key, actual[key], config["expected_sha256"][key], " ACCEPTED" if key in mismatched else ""))
    elif mismatched:
        for key in mismatched:
            print("tool_hash %s actual=%s expected=%s MISMATCH" % (key, actual[key], config["expected_sha256"][key]),
                  file=sys.stderr)
        raise ToolError(EXIT_TOOL_HASH_MISMATCH,
                        "tool hash mismatch for %s (use --accept-tool-hashes to run anyway; the config is not edited)"
                        % ", ".join(mismatched))
    return actual, mismatched


def find_clang(config, runtime_sha256=None, locks=None):
    """Return (clang executable or None, resource include directory Path) for the configured shape:
    the pinned manifest admission (`locks` holds the inputs for the run) or the discovery."""
    if set(config["clang_resource"]) == set(MANIFEST_KEYS):
        return admit_toolchain(config, runtime_sha256, locks)
    return discover_clang(config)


def discover_clang(config):
    """Discovery: `resource_dir`, or the `clang_candidates` tried in order (last match of a glob first)."""
    clang = config["clang_resource"]
    timeout = config["timeouts_seconds"]["clang"]
    if clang["resource_dir"] is not None:
        resource = Path(expand(clang["resource_dir"], "clang_resource.resource_dir"))
        return None, check_resource(resource, clang["required_major"])
    problems = []
    for candidate in clang["clang_candidates"]:
        try:
            text = expand(candidate, "clang candidate")
        except ToolError:
            problems.append("%s: variable unset" % candidate)
            continue
        if "*" in text:
            exe_list = [Path(m) for m in sorted(glob.glob(text)) if os.path.isfile(m)]
        elif os.sep in text or "/" in text:
            exe_list = [Path(text)] if Path(text).is_file() else []
        else:
            found = shutil.which(text)
            exe_list = [Path(found)] if found else []
        for exe in reversed(exe_list):
            try:
                code, out, _ = run_process("clang -print-resource-dir", [exe, "-print-resource-dir"], timeout, REPO_ROOT)
            except ToolError as error:
                problems.append("%s: %s" % (exe, error.message))
                continue
            if code != 0 or not out.strip():
                problems.append("%s: -print-resource-dir failed" % exe)
                continue
            try:
                return exe, check_resource(Path(out.strip()), clang["required_major"])
            except ToolError as error:
                problems.append("%s: %s" % (exe, error.message))
    raise ToolError(EXIT_CLANG_UNAVAILABLE, "no usable clang found: " + "; ".join(problems or ["no candidate exists"]))


def check_resource(resource, major):
    include = resource / "include"
    if not (include / "stddef.h").is_file() or not (include / "stdint.h").is_file():
        raise ToolError(EXIT_CLANG_UNAVAILABLE, "resource directory %s has no freestanding headers" % resource)
    if resource.name != major:
        raise ToolError(EXIT_CLANG_UNAVAILABLE, "resource directory %s is not clang major %s" % (resource, major))
    return include


def toolchain_member(root, relative):
    """Resolve only manifest-owned ordinary paths; never follow reparse points."""
    require(isinstance(relative, str) and relative and not relative.startswith("/"),
            "toolchain member must be a relative path")
    parts = relative.split("/")
    require(all(re.fullmatch(r"[A-Za-z0-9_.+-]+", part) and part not in (".", "..")
                and not part.endswith((".", " ")) for part in parts),
            "unsafe toolchain member path: %r" % relative)
    path = root.joinpath(*parts)
    for ancestor in (path, *path.parents):
        if ancestor.exists() and is_link(ancestor):
            raise ToolError(EXIT_CLANG_UNAVAILABLE, "toolchain reparse input: %s" % ancestor)
    return path


@contextmanager
def lock_toolchain_input(path, directory=False):
    """Keep selected Windows input bytes and path parents stable through Gate."""
    if os.name != "nt":
        raise ToolError(EXIT_CLANG_UNAVAILABLE, "native toolchain locking requires Windows")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0 if directory else 0x80000000, 1,
                                None, 3, 0x00200000 | (0x02000000 if directory else 0), None)
    if handle == ctypes.c_void_p(-1).value:
        raise ToolError(EXIT_CLANG_UNAVAILABLE, "cannot lock toolchain input: %s (winerror %s)" %
                        (path, ctypes.get_last_error()))
    try:
        if is_link(path):
            raise ToolError(EXIT_CLANG_UNAVAILABLE, "toolchain reparse input: %s" % path)
        yield
    finally:
        kernel.CloseHandle(handle)


def toolchain_inventory(root, manifest_path):
    observed = set()
    for directory, subdirs, files in os.walk(root, followlinks=False):
        for name in subdirs + files:
            path = Path(directory) / name
            if is_link(path):
                raise ToolError(EXIT_CLANG_UNAVAILABLE, "toolchain reparse input: %s" % path)
        for name in files:
            path = Path(directory) / name
            if path != manifest_path:
                observed.add(path.relative_to(root).as_posix())
    return observed


def admit_toolchain(config, runtime_sha256, locks):
    """Admit one explicitly pinned compiler/resource set for the actual runtime."""
    selection = config["clang_resource"]
    manifest_path = Path(expand(selection["manifest"], "clang_resource.manifest"))
    require(manifest_path.is_absolute(), "clang_resource.manifest must be absolute")
    try:
        raw = manifest_path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == selection["manifest_sha256"],
                "native toolchain provenance digest differs from configured identity")
        record = json.loads(raw)
        check_keys(record, "native toolchain", ("kind", "source", "compiler", "semantic_runtime",
                                                "resource_directory", "files"))
        require(record["kind"] == "native_c_toolchain_inputs", "unexpected toolchain manifest kind")
        check_keys(record["source"], "toolchain source", ("release_url", "release_tag", "archive_url",
                                                          "archive_name", "archive_size", "archive_sha256"))
        require(all(isinstance(record["source"][key], str) and record["source"][key]
                    for key in ("release_url", "release_tag", "archive_url", "archive_name")),
                "toolchain source identity is incomplete")
        require(SHA256_PATTERN.fullmatch(record["source"]["archive_sha256"]) is not None
                and type(record["source"]["archive_size"]) is int and record["source"]["archive_size"] > 0,
                "toolchain archive identity is invalid")
        root = manifest_path.parent
        toolchain_member(root, manifest_path.name)
        require(isinstance(record["files"], list) and record["files"], "toolchain files are absent")
        members = {}
        folded = set()
        for member in record["files"]:
            check_keys(member, "toolchain file", ("path", "size", "sha256"))
            path = toolchain_member(root, member["path"])
            require(member["path"].casefold() not in folded and path != manifest_path,
                    "duplicate or manifest-alias toolchain member")
            folded.add(member["path"].casefold())
            require(type(member["size"]) is int and member["size"] >= 0
                    and isinstance(member["sha256"], str)
                    and SHA256_PATTERN.fullmatch(member["sha256"]) is not None,
                    "invalid toolchain file identity")
            members[member["path"]] = (path, member)
        compiler = toolchain_member(root, record["compiler"])
        runtime = toolchain_member(root, record["semantic_runtime"])
        resource = toolchain_member(root, record["resource_directory"]) / "include"
        require(record["compiler"] in members and record["semantic_runtime"] in members,
                "compiler/runtime absent from toolchain inventory")
        require(members[record["semantic_runtime"]][1]["sha256"] == runtime_sha256,
                "toolchain semantic runtime differs from installed libclang")
        require(runtime == members[record["semantic_runtime"]][0], "toolchain semantic runtime path differs")
        directories = {root, *root.parents}
        for path, _ in members.values():
            directories.update(path.parents)
        for directory in sorted(directories, key=lambda path: (len(path.parts), str(path))):
            locks.enter_context(lock_toolchain_input(directory, True))
        locks.enter_context(lock_toolchain_input(manifest_path))
        require(manifest_path.read_bytes() == raw, "toolchain provenance changed during admission")
        for path, member in members.values():
            locks.enter_context(lock_toolchain_input(path))
            require(path.is_file() and path.stat().st_size == member["size"]
                    and sha256_file(path) == member["sha256"], "toolchain member changed: %s" % path)
        require(toolchain_inventory(root, manifest_path) == set(members),
                "toolchain directory differs from its complete inventory")
        require((resource / "stddef.h").is_file() and (resource / "stdint.h").is_file(),
                "toolchain resource headers are absent")
        config["_resource_members"] = {str(path.resolve()).casefold(): member["sha256"]
                                       for path, member in members.values()}
        config["_native_toolchain"] = {
            "manifest": str(manifest_path), "manifest_sha256": selection["manifest_sha256"],
            "source": record["source"], "compiler": str(compiler),
            "compiler_sha256": members[record["compiler"]][1]["sha256"],
            "semantic_runtime_sha256": runtime_sha256, "resource_include": str(resource),
            "member_count": len(members)}
        config["_native_toolchain_manifest"] = record
        config["_toolchain_inventory_check"] = lambda: require(
            toolchain_inventory(root, manifest_path) == set(members), "toolchain inventory changed during execution")
        return compiler, resource
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ToolError(EXIT_CLANG_UNAVAILABLE, "native toolchain input unavailable: %s" % error) from error


# ---------------------------------------------------------------- Cell and output

def check_cell(cell_argument):
    cell = checked_original_path(cell_argument)
    if not cell.is_dir():
        raise ToolError(EXIT_CELL_INVALID, "Cell root %s is not a directory" % cell)
    if is_link(cell):
        raise ToolError(EXIT_CELL_INVALID, "Cell root %s is a link or reparse point" % cell)
    manifest = cell / "comsect1.json"
    if not manifest.is_file() or is_link(manifest):
        raise ToolError(EXIT_CELL_INVALID, "%s is not a regular file; not a Cell" % manifest)
    units = []
    for directory, subdirs, files in os.walk(cell, followlinks=False):
        subdirs.sort()
        for entry in subdirs + files:
            if is_link(os.path.join(directory, entry)):
                raise ToolError(EXIT_CELL_INVALID, "link or reparse point inside the Cell: %s" % os.path.join(directory, entry))
        for entry in files:
            if entry.endswith(".c"):
                units.append(Path(directory) / entry)
    if not units:
        raise ToolError(EXIT_CELL_INVALID, "Cell %s has no C translation unit" % cell)
    units.sort(key=lambda p: p.relative_to(cell).as_posix())
    return cell, units


def prepare_output(run_id, cell):
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ToolError(EXIT_OUTPUT_INVALID, "run id must match %s" % RUN_ID_PATTERN.pattern)
    parent = REPO_ROOT
    for part in ("90_temps", "verification", "native_gate"):
        parent = parent / part
        if parent.exists():
            if not parent.is_dir() or is_link(parent):
                raise ToolError(EXIT_OUTPUT_INVALID, "%s is a link or not a directory" % parent)
    run_dir = parent / run_id
    if run_dir.exists():
        raise ToolError(EXIT_OUTPUT_INVALID, "output directory %s already exists" % run_dir)
    resolved = parent.resolve() / run_id
    if cell == resolved or resolved in cell.parents or cell in resolved.parents:
        raise ToolError(EXIT_OUTPUT_INVALID, "output directory and Cell must not contain each other")
    return run_dir


def create_output(run_dir):
    try:
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        for ancestor in (run_dir.parent, run_dir.parent.parent, run_dir.parent.parent.parent):
            if is_link(ancestor):
                raise ToolError(EXIT_OUTPUT_INVALID, "%s is a link" % ancestor)
        run_dir.mkdir()
    except OSError as error:
        raise ToolError(EXIT_OUTPUT_INVALID, "cannot create %s: %s" % (run_dir, error))


# ---------------------------------------------------------------- plan

def native_path(path):
    text = str(Path(path).resolve()).replace("\\", "/")
    if re.match(r"[A-Za-z]:/", text) is None:
        raise ToolError(EXIT_PLAN_FAILED, "path %s has no drive letter" % text)
    return "fs/%s/%s" % (text[0].upper(), text[3:])


def include_directories(config, cell):
    """Include roots in compiler order: the Cell's own, then the dependency membranes.

    A dependency membrane lies outside the Cell, inside this repository; its files
    enter the closure as external inputs and are never governed by this Cell."""
    result = []
    for rule in config["build"]["include_roots"]:
        directory = checked_original_path(cell / rule)
        if cell != directory and cell not in directory.parents or not directory.is_dir():
            raise ToolError(EXIT_PLAN_FAILED, "include root %r is not a directory inside the Cell" % rule)
        result.append(directory)
    for rule in config["build"]["external_include_roots"]:
        directory = checked_original_path(REPO_ROOT / rule) if (REPO_ROOT / rule).exists() else (REPO_ROOT / rule)
        if REPO_ROOT.resolve() not in directory.parents or not directory.is_dir() \
                or cell == directory or cell in directory.parents or directory in cell.parents:
            raise ToolError(EXIT_PLAN_FAILED,
                            "external include root %r is not a directory of this repository outside the Cell" % rule)
        if is_link(directory):
            raise ToolError(EXIT_PLAN_FAILED, "external include root %r is a link or reparse point" % rule)
        result.append(directory)
    return result


def system_directories(config):
    """External SDK include roots (read only), searched after the clang resource directory, so
    the freestanding headers resolve to the resource directory and the SDK headers to the SDK."""
    result = []
    for root in config["build"]["system_include_roots"]:
        directory = checked_original_path(root) if Path(root).exists() else Path(root)
        if not directory.is_dir():
            raise ToolError(EXIT_PLAN_FAILED, "system include root %r is not a directory" % root)
        if REPO_ROOT.resolve() in directory.parents or directory == REPO_ROOT.resolve():
            raise ToolError(EXIT_PLAN_FAILED, "system include root %r lies inside this repository" % root)
        if is_link(directory):
            raise ToolError(EXIT_PLAN_FAILED, "system include root %r is a link or reparse point" % root)
        result.append(directory)
    return result


def compile_flags(config, roots):
    build = config["build"]
    flags = ["--target=" + build["target"], "-std=" + build["standard"], "-ffreestanding",
             "-f%s-char" % build["plain_char"]]
    for name, value in build["definitions"].items():
        flags.append("-D%s=%s" % (name, value))
    for root in roots:
        flags += ["-I", str(root)]
    return flags


def header_closure(config, clang, resource_include, roots, entry, cwd):
    command = [clang] + compile_flags(config, roots) + ["-M", "-nostdinc", "-isystem", resource_include]
    for system_root in system_directories(config):
        command += ["-isystem", str(system_root)]
    command.append(entry)
    code, out, err = run_process("clang -M", command, config["timeouts_seconds"]["clang"], cwd)
    if code != 0:
        raise ToolError(EXIT_PLAN_FAILED, "clang -M failed for %s: %s" % (entry, err.strip()))
    tokens = re.findall(r"(?:\\ |\S)+", re.sub(r"\\\r?\n", " ", out))[1:]
    return sorted({str(checked_original_path(Path(token.replace("\\ ", " "))
                   if Path(token.replace("\\ ", " ")).is_absolute()
                   else Path(cwd) / token.replace("\\ ", " "))) for token in tokens})


def configuration_for(config, clang, resource_include, roots, cell, entry, cwd):
    build = config["build"]
    governed, external, inputs = [], [], {}
    admitted = config.get("_resource_members")
    for file in header_closure(config, clang, resource_include, roots, entry, cwd):
        path = Path(file)
        if admitted is not None and (resource_include == path or resource_include in path.parents):
            require(str(path.resolve()).casefold() in admitted,
                    "header closure selected an unadmitted resource member: %s" % path)
        if path == cell or cell in path.parents:
            governed.append({"native_path": native_path(path), "cell_path": path.relative_to(cell).as_posix()})
        else:
            location = native_path(path)
            # A short stable id: a large SDK closure would overflow the command line of
            # comsect1-native-input (32767 characters on Windows) if every id repeated its path;
            # 64 bits of the path digest keep a hosted closure inside it. Two paths of one closure
            # with one id are refused.
            identifier = "x" + sha256_text(location)[:16]
            if identifier in inputs:
                raise ToolError(EXIT_PLAN_FAILED, "external input id %s repeats for %s" % (identifier, location))
            external.append({"native_path": location, "external_input_id": identifier})
            inputs[identifier] = file
    if not governed:
        raise ToolError(EXIT_PLAN_FAILED, "closure of %s has no Cell file" % entry)
    relative = entry.relative_to(cell).as_posix()
    return {
        "configuration_id": re.sub(r"[^A-Za-z0-9_.-]", "_", relative),
        "publication_authority_id": None,
        "virtual_root": build["virtual_root"],
        "target": build["target"],
        "standard": build["standard"],
        "plain_char": build["plain_char"],
        "forced_includes": [],
        "entry": native_path(entry),
        "include_roots": [native_path(root) for root in roots] + [native_path(resource_include)]
                         + [native_path(root) for root in system_directories(config)],
        "definitions": dict(build["definitions"]),
        "preprocessing_epoch_seconds": build["preprocessing_epoch_seconds"],
        "governed_inputs": governed,
        "external_inputs": external,
        "configured_candidate_paths": [item["cell_path"] for item in governed],
    }, inputs


# ---------------------------------------------------------------- lanes

def report_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Gate report key: %s" % key)
        result[key] = value
    return result


def report_constant(value):
    raise ValueError("non-finite Gate report constant: %s" % value)


def read_report(report_path, gate_text, gate_code):
    """The lane result of one Gate report: unique keys, finite numbers, known verdict and handoff, the
    finding count of the list, the outcome summary with every count, an exit code of the Gate set, and
    a verdict that agrees with the exit code; a blocked assessment keeps BLOCK."""
    if not report_path.is_file():
        raise ToolError(EXIT_GATE_REFUSED, "Gate wrote no report (exit %d): %s" % (gate_code, gate_text.strip()[:400]))
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"),
                            object_pairs_hook=report_object, parse_constant=report_constant)
        verdict, count, handoff, findings = report["verdict"], report["finding_count"], report["handoff"], report["findings"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ToolError(EXIT_GATE_REFUSED, "Gate report unusable: %s" % error)
    if not (isinstance(verdict, str) and isinstance(handoff, str) and isinstance(findings, list)
            and type(count) is int):
        raise ToolError(EXIT_GATE_REFUSED, "Gate report has unexpected member types")
    if count != len(findings):
        raise ToolError(EXIT_GATE_REFUSED, "Gate finding count differs from the findings list")
    outcome = report.get("outcome_summary")
    if not (verdict in ("PASS", "WARN", "REQ", "INDETERMINATE", "FAIL")
            and handoff in ("CONTINUE", "CONTINUE_WITH_RISK", "BLOCK")
            and count >= 0 and all(isinstance(f, dict) for f in findings)
            and isinstance(outcome, dict) and type(outcome.get("assessment_blocked")) is bool
            and all(type(outcome.get(k)) is int and 0 <= outcome[k] <= count for k in COUNT_NAMES)
            and type(gate_code) is int and gate_code in (0, 1, 3, 4)):
        raise ToolError(EXIT_GATE_REFUSED, "Gate report has unexpected member types")
    codes = {}
    for finding in findings:
        code = finding.get("code")
        codes[str(code)] = codes.get(str(code), 0) + 1
    if verdict == "PASS" and (gate_code != 0 or count != 0):
        raise ToolError(EXIT_GATE_REFUSED, "inconsistent Gate result: verdict PASS, exit %d, findings %d" % (gate_code, count))
    if verdict == "PASS" and handoff != "CONTINUE":
        raise ToolError(EXIT_GATE_REFUSED, "inconsistent Gate result: verdict PASS with handoff %s" % handoff)
    if verdict == "PASS" and outcome["assessment_blocked"]:
        raise ToolError(EXIT_GATE_REFUSED, "inconsistent Gate result: verdict PASS with a blocked assessment")
    if verdict != "PASS" and gate_code == 0:
        raise ToolError(EXIT_GATE_REFUSED, "inconsistent Gate result: verdict %s with exit 0" % verdict)
    if (outcome["assessment_blocked"] or outcome["assessment_count"]) and (verdict not in ("INDETERMINATE", "FAIL") or handoff != "BLOCK"):
        raise ToolError(EXIT_GATE_REFUSED, "incomplete assessment lost its blocking result")
    return {"verdict": verdict, "finding_count": count, "handoff": handoff, "gate_exit": gate_code,
            "finding_codes": dict(sorted(codes.items())), "outcome_summary": outcome,
            "report_sha256": sha256_file(report_path)}


def verdict_exit(verdict):
    if verdict == "PASS":
        return EXIT_PASS
    if verdict == "FAIL":
        return EXIT_FAIL
    if verdict == "INDETERMINATE":
        return EXIT_INDETERMINATE
    raise ToolError(EXIT_GATE_REFUSED, "unknown Gate verdict %r" % verdict)


def gate_command(gate, cell, report, review):
    return [gate, "check", "--root", cell, "--cell", "--out", report, "--review-out", review, "--quiet"]


def run_plain_lane(config, paths, cell, lane_dir):
    lane_dir.mkdir()
    command = gate_command(paths["gate"], cell, lane_dir / "report.json", lane_dir / "review.json")
    code, out, err = run_process("gate (plain)", command, config["timeouts_seconds"]["gate"], lane_dir, lane_dir / "gate.txt")
    return read_report(lane_dir / "report.json", out + err, code)


def input_owner_selection(config, inputs, cell):
    """Select actual external source Cells and explicitly configured SDKs.

    Only original ancestry identifies a Cell. The owner CLI validates controls,
    public entries, support and inventory; this driver does not create receipts.
    Selections are per translation unit, so unused owners are never submitted.
    """
    publications = []
    for record in config.get("publications", []):
        root = Path(expand(record["canonical_root"], "publication.canonical_root"))
        if not root.is_absolute() or ".." in root.parts or not root.is_dir():
            raise ToolError(EXIT_PLAN_FAILED, "publication root must be an existing absolute directory")
        root = checked_original_path(root)
        if any(root == other or root in other.parents or other in root.parents
               for other, _ in publications):
            raise ToolError(EXIT_PLAN_FAILED, "overlapping publication roots are ambiguous")
        publications.append((root, dict(record, canonical_root=root.as_posix())))
    selected, sources, controls = {}, set(), {}
    for value in inputs.values():
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or not path.is_file():
            raise ToolError(EXIT_PLAN_FAILED, "external input must be an existing absolute file")
        path = checked_original_path(path)
        matches = [(root, record) for root, record in publications if root in path.parents]
        if matches:
            root, record = matches[0]
            selected[root] = record
            continue
        owners = []
        for directory in path.parents:
            if directory not in controls:
                control = directory / "comsect1.json"
                present = os.path.lexists(control)
                if present and (is_link(control) or not control.is_file()):
                    raise ToolError(EXIT_PLAN_FAILED, "invalid original Cell control: %s" % control)
                controls[directory] = present
            if controls[directory]:
                owners.append(directory)
        if len(owners) > 1:
            raise ToolError(EXIT_PLAN_FAILED, "nested original Cell controls: %s" % path)
        if owners:
            if owners[0] == cell:
                raise ToolError(EXIT_PLAN_FAILED, "governed Cell input cannot be external")
            sources.add(owners[0])
    return sorted(sources, key=str), [selected[root] for root in sorted(selected, key=str)]


def run_native_lane(config, paths, cell, units, clang, resource_include, lane_dir):
    lane_dir.mkdir()
    roots = include_directories(config, cell)
    configs, inputs_of, receipts = [], {}, []
    for entry in units:
        item, inputs = configuration_for(config, clang, resource_include, roots, cell, entry, lane_dir)
        configs.append(item)
        inputs_of[item["configuration_id"]] = inputs
    ids = [item["configuration_id"] for item in configs]
    if len(set(ids)) != len(ids):
        raise ToolError(EXIT_PLAN_FAILED, "configuration ids are not unique")
    plan_path = lane_dir / "plan.json"
    plan = {"schema": "comsect1.gate.native-analysis-plan",
            "targets": [{"cell_root": str(cell).replace("\\", "/"), "configurations": configs}]}
    timeout = config["timeouts_seconds"]["native_input"]
    for item in configs:
        write_json(plan_path, plan)
        cid = item["configuration_id"]
        receipt = lane_dir / ("receipt-%s.json" % cid)
        command = [paths["native_input"], "--plan", plan_path, "--configuration", cid,
                   "--snapshot", lane_dir / ("snapshot-" + cid), "--receipt", receipt]
        for key, path in inputs_of[cid].items():
            command += ["--input", "%s=%s" % (key, path)]
        sources, publications = input_owner_selection(config, inputs_of[cid], cell)             if "publications" in config else ([], [])
        for source in sources:
            command += ["--source-cell", source]
        for index, publication in enumerate(publications):
            descriptor = lane_dir / ("publication-%s-%d.json" % (cid, index))
            write_json(descriptor, publication)
            command += ["--publication", descriptor]
        code, out, err = run_process("native-input " + cid, command, timeout, lane_dir,
                                     lane_dir / ("native-input-%s.txt" % cid))
        authority = out.strip()
        if code != 0 or AUTHORITY_PATTERN.fullmatch(authority) is None:
            raise ToolError(EXIT_NATIVE_INPUT_FAILED, "native-input failed for %s (exit %d): %s" % (cid, code, err.strip()[:400]))
        item["publication_authority_id"] = authority
        receipts.append(receipt)
    write_json(plan_path, plan)
    command = [paths["gate"], "check", "--root", cell, "--cell", "--native-analysis", plan_path,
               "--out", lane_dir / "report.json", "--review-out", lane_dir / "review.json", "--quiet"]
    for receipt in receipts:
        command += ["--native-publication-receipt", receipt]
    code, out, err = run_process("gate (native)", command, config["timeouts_seconds"]["gate"], lane_dir, lane_dir / "gate.txt")
    result = read_report(lane_dir / "report.json", out + err, code)
    result["plan_sha256"] = sha256_file(plan_path)
    result["translation_units"] = len(configs)
    return result


def lane_line(name, result):
    if "error" in result:
        return "%s: ERROR class=%s code=%d %s" % (name, EXIT_NAMES[result["exit"]], result["exit"], result["error"])
    codes = ",".join("%s:%d" % item for item in result["finding_codes"].items()) or "-"
    return "%s: verdict=%s findings=%d handoff=%s gate_exit=%d codes=%s" % (
        name, result["verdict"], result["finding_count"], result["handoff"], result["gate_exit"], codes)


# ---------------------------------------------------------------- main

def parse_arguments(argv):
    parser = argparse.ArgumentParser(prog="native_gate.py", description="Run the native C Gate lane on one Cell.")
    parser.add_argument("--cell", required=True, help="Cell root (read only; may be outside this repository)")
    parser.add_argument("--config", required=True, help="lane configuration JSON")
    parser.add_argument("--lane", choices=("native", "plain", "both"), default="native")
    parser.add_argument("--run-id", default=None, help="run id (default: UTC timestamp)")
    parser.add_argument("--accept-tool-hashes", action="store_true",
                        help="print actual tool hashes and continue on mismatch; the config is not edited")
    parser.add_argument("--accept-tool-drift", action="store_true",
                        help="run although the maintainer tools differ from their template manifest (recorded)")
    return parser.parse_args(argv)


def maintainer_tools(accept_drift):
    try:
        return maint_config.maintainer_tools(str(REPO_ROOT), accept_drift)
    except maint_config.ConfigError as error:
        raise ToolError(EXIT_CONFIG, str(error))


def run(arguments):
    config = load_config(arguments.config)
    tools = maintainer_tools(arguments.accept_tool_drift)
    cell, units = check_cell(arguments.cell)
    run_id = arguments.run_id or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = prepare_output(run_id, cell)
    _, paths, set_id = resolve_gate_set(config)
    hashes, accepted = check_tool_hashes(config, paths, arguments.accept_tool_hashes)
    manifest_mode = config["_clang_mode"] == "manifest"
    with ExitStack() as locks:
        clang, resource_include = (None, None)
        if arguments.lane in ("native", "both"):
            clang, resource_include = find_clang(config, hashes["libclang"], locks)
            if clang is None:
                raise ToolError(EXIT_CLANG_UNAVAILABLE, "header closure needs a clang executable; set clang_candidates")
        create_output(run_dir)
        if clang is not None and manifest_mode:
            write_json(run_dir / "toolchain_provenance.json", config["_native_toolchain_manifest"])
        lanes = ("native", "plain") if arguments.lane == "both" else (arguments.lane,)
        results, code = {}, EXIT_PASS
        for lane in lanes:
            try:
                if lane == "native":
                    results[lane] = run_native_lane(config, paths, cell, units, clang, resource_include, run_dir / "native")
                else:
                    results[lane] = run_plain_lane(config, paths, cell, run_dir / "plain")
                lane_code = verdict_exit(results[lane]["verdict"])
            except ToolError as error:
                results[lane] = {"error": error.message, "exit": error.code}
                lane_code = error.code
            print(lane_line(lane, results[lane]))
            code = max(code, lane_code)
        if clang is not None and manifest_mode:
            config["_toolchain_inventory_check"]()
        summary = {
            "run_id": run_id, "lane": arguments.lane, "exit": code, "exit_class": EXIT_NAMES[code],
            "release_set_id": set_id, "tool_sha256": hashes, "tool_hash_mismatch_accepted": accepted,
            "config_sha256": config["_sha256"], "cell_manifest_sha256": sha256_file(cell / "comsect1.json"),
            "standard": config["build"]["standard"], "target": config["build"]["target"],
        }
        if manifest_mode:
            summary["native_toolchain"] = config.get("_native_toolchain")
        summary["maintainer_tools"] = tools
        summary["lanes"] = results
        write_json(run_dir / "summary.json", summary)
        print("run_dir=%s exit=%d %s" % (run_dir.relative_to(REPO_ROOT).as_posix(), code, EXIT_NAMES[code]))
        return code


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
    try:
        arguments = parse_arguments(argv)
    except SystemExit as stop:
        return EXIT_USAGE if stop.code not in (0, None) else 0
    try:
        return run(arguments)
    except ToolError as error:
        print("native_gate: %s: %s" % (EXIT_NAMES[error.code], error.message), file=sys.stderr)
        return error.code
    except Exception as error:  # fail closed on anything unexpected
        import traceback
        traceback.print_exc()
        print("native_gate: INTERNAL: %s" % error, file=sys.stderr)
        return EXIT_INTERNAL
