# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Kim Hyeongjeong (comsect1)
"""Fixture child for the run_process timeout test: starts a grandchild and sleeps."""
import subprocess
import sys
import time

if len(sys.argv) > 1 and sys.argv[1] == "grandchild":
    time.sleep(120)
else:
    subprocess.Popen([sys.executable, "-I", "-B", __file__, "grandchild"], stdin=subprocess.DEVNULL)
    time.sleep(120)
