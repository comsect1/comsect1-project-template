# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Check and normalize repository text files under the `.gitattributes` LF policy (Python standard library only).

Run from any directory inside a Git worktree:

    python -I -B 20_ops/tools/text_format.py
    python -I -B 20_ops/tools/text_format.py --apply

The check is read-only and exits 1 when a tracked or untracked non-ignored file
carrying the `eol=lf` attribute is non-UTF-8, starts with a UTF-8 BOM, has CRLF,
CR or mixed line endings, or lacks a final LF newline. `--apply` rewrites only
decodable UTF-8 files that have a UTF-8 BOM, non-LF line endings, or a missing
final newline without staging them; it refuses symbolic links, reparse points,
paths outside the repository root, and undecodable non-UTF-8 files.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

ROW_PATTERN = re.compile(r"^i/\S*\s+w/(?P<work>\S+)\s+attr/(?P<attributes>.*?)\t(?P<path>.*)$")
EOL_LF_PATTERN = re.compile(r"(^|\s)eol=lf($|\s)")
REPARSE_FLAG = 0x400
CREATE_NO_WINDOW = 0x08000000


class TextFormatError(Exception):
    """The Git worktree or a governed file cannot be inspected or rewritten safely."""


def _window_flags() -> int:
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def _is_link(path: str) -> bool:
    if not os.path.lexists(path):
        return False
    info = os.lstat(path)
    return (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & REPARSE_FLAG)
        or (hasattr(os.path, "isjunction") and os.path.isjunction(path))
    )


def _resolve_safe_repo_path(repo_root: str, relative_path: str) -> str:
    if not relative_path or os.path.isabs(relative_path) or ":" in relative_path:
        raise TextFormatError(f"Tracked path escapes repository root: {relative_path}")
    parts = relative_path.replace("\\", "/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise TextFormatError(f"Tracked path escapes repository root: {relative_path}")
    root_abs = os.path.abspath(repo_root)
    root_prefix = root_abs.rstrip(os.sep) + os.sep
    candidate = os.path.abspath(os.path.join(root_abs, *parts))
    if not os.path.normcase(candidate).startswith(os.path.normcase(root_prefix)):
        raise TextFormatError(f"Tracked path escapes repository root: {relative_path}")
    cursor = candidate
    while os.path.normcase(cursor) != os.path.normcase(root_abs):
        if _is_link(cursor):
            raise TextFormatError(f"Refusing to operate on symbolic link or reparse point: {relative_path}")
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    return candidate


def find_repository_root(start_dir: str | None = None) -> str:
    candidates = [os.path.abspath(start_dir)] if start_dir else [
        os.path.dirname(os.path.abspath(__file__)),
        os.path.abspath(os.getcwd()),
    ]
    last_exc: Exception | None = None
    for cwd in candidates:
        try:
            proc = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=60,
                creationflags=_window_flags(),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            last_exc = exc
            continue
        root = proc.stdout.strip()
        if proc.returncode == 0 and root and os.path.isdir(root):
            return os.path.abspath(root)
    if last_exc is not None:
        raise TextFormatError(f"The text_format tool must run inside a Git worktree: {last_exc}") from last_exc
    raise TextFormatError("The text_format tool must run inside a Git worktree.")


def get_non_canonical_text(repo_root: str) -> list[tuple[str, str]]:
    """Return `[(problem, relative_path)]` for files governed by `eol=lf`."""
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                repo_root,
                "-c",
                "core.quotepath=false",
                "ls-files",
                "--eol",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=120,
            creationflags=_window_flags(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise TextFormatError(f"git ls-files --eol failed: {exc}") from exc
    if proc.returncode != 0:
        raise TextFormatError(f"git ls-files --eol failed: {proc.stderr.strip()}")

    findings: list[tuple[str, str]] = []
    for raw_line in proc.stdout.splitlines():
        match = ROW_PATTERN.match(raw_line)
        if not match:
            continue
        work_ending = match.group("work")
        attributes = match.group("attributes")
        relative_path = match.group("path")
        if not EOL_LF_PATTERN.search(attributes):
            continue
        if work_ending == "-text":
            continue
        path = _resolve_safe_repo_path(repo_root, relative_path)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            source = handle.read()
        try:
            source.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            findings.append(("NON_UTF8", relative_path))
            continue
        if source.startswith(b"\xef\xbb\xbf"):
            findings.append(("UTF8_BOM", relative_path))
            continue
        if work_ending in ("crlf", "mixed", "cr"):
            findings.append((work_ending.upper(), relative_path))
            continue
        if b"\r" in source:
            findings.append(("CRLF" if b"\r\n" in source else "CR", relative_path))
            continue
        if len(source) > 0 and source[-1] != 0x0A:
            findings.append(("NO_FINAL_NEWLINE", relative_path))
    return findings


def convert_text_to_lf(repo_root: str, relative_path: str) -> None:
    """Normalize UTF-8 BOM, CR/CRLF line endings, and final newline in place."""
    path = _resolve_safe_repo_path(repo_root, relative_path)
    with open(path, "rb") as handle:
        source = handle.read()
    if source.startswith(b"\xef\xbb\xbf"):
        source = source[3:]
    normalized = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if len(normalized) > 0 and not normalized.endswith(b"\n"):
        normalized += b"\n"
    with open(path, "wb") as handle:
        handle.write(normalized)


def _print_findings_table(findings: list[tuple[str, str]]) -> None:
    prob_width = max(len("Problem"), *(len(p) for p, _ in findings))
    print(f"{'Problem':<{prob_width}}  Path")
    print(f"{'-' * prob_width}  ----")
    for problem, rel_path in findings:
        print(f"{problem:<{prob_width}}  {rel_path}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
    parser = argparse.ArgumentParser(
        prog="text_format.py",
        description="Verify or normalize UTF-8 (no BOM) and LF line endings under .gitattributes policy.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Normalize UTF-8 BOM, CRLF/CR line endings, and missing final LF in place without staging.",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = find_repository_root()
        findings = get_non_canonical_text(repo_root)
        if not findings:
            print("text format: PASS (tracked and untracked LF policy files are canonical)")
            return 0

        if not args.apply:
            _print_findings_table(findings)
            print(
                f"text format: FAIL ({len(findings)} file(s)); rerun with --apply to normalize",
                file=sys.stderr,
            )
            return 1

        for problem, relative_path in findings:
            if problem == "NON_UTF8":
                print(f"WARNING: refusing to guess source encoding for {relative_path}", file=sys.stderr)
                continue
            convert_text_to_lf(repo_root, relative_path)
            print(f"normalized {relative_path}")

        remaining = get_non_canonical_text(repo_root)
        if remaining:
            _print_findings_table(remaining)
            print(
                f"text format: FAIL ({len(remaining)} file(s) remain noncanonical)",
                file=sys.stderr,
            )
            return 1

        print(f"text format: PASS (normalized {len(findings)} file(s); changes are not staged)")
        return 0
    except TextFormatError as exc:
        print(f"text format: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
