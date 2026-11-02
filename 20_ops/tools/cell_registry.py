# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Entry `cell_registry.py`: the implementation is `comsect1_maint.registry` (template common layer, never edited here).

The package is loaded by file path from the folder beside this file, never
through `sys.path`; every public and underscore name of the module is
reachable here, so a consumer that loads this file by path sees the module.
A test that patches a module global patches `comsect1_maint.registry`.
"""
import importlib
import importlib.util
import pathlib
import sys

_root = pathlib.Path(__file__).resolve().parent / "comsect1_maint"
_package = sys.modules.get("comsect1_maint")
if _package is None:
    _spec = importlib.util.spec_from_file_location("comsect1_maint", _root / "__init__.py",
                                                   submodule_search_locations=[str(_root)])
    _package = importlib.util.module_from_spec(_spec)
    sys.modules["comsect1_maint"] = _package
    _spec.loader.exec_module(_package)
elif [pathlib.Path(path).resolve() for path in _package.__path__] != [_root]:
    raise ImportError("comsect1_maint is loaded from %s, not %s" % (list(_package.__path__), _root))
_implementation = importlib.import_module("comsect1_maint.registry")
globals().update({k: v for k, v in vars(_implementation).items() if not k.startswith("__")})
