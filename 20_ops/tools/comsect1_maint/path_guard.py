# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Check actual path traversal before canonicalization; no Cell authority."""
import os
from pathlib import Path
import stat


def _checked_info(path):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400
            or (hasattr(os.path, 'isjunction') and os.path.isjunction(path))):
        raise ValueError('linked or reparse path component: ' + str(path))
    return info


def checked_path(value):
    path = Path(value)
    if not path.is_absolute():
        if path.drive or path.root:
            raise ValueError('ambiguous rooted or drive-relative path: ' + str(path))
        path = Path.cwd() / path
    current = Path(path.anchor)
    info = _checked_info(current)
    for part in path.parts[1:]:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('non-directory path component: ' + str(current))
        current = current.parent if part == '..' else current / part
        info = _checked_info(current)
    return current.resolve(strict=True)
