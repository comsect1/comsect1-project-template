# Temporary Output and Cleanup

Use only these disposable roots:

```text
90_temps/build/<tool>/<run-id>/
90_temps/verification/<run-id>/
90_temps/validation/<run-id>/
90_temps/generation/<run-id>/
90_temps/release/<run-id>/
90_temps/scratch/<run-id>/
99_trash/<cleanup-id>/
```

For cleanup, close producers; enumerate the exact task-owned run; resolve and
validate source and destination; reject aliases, links, mounts, junctions, and
reparse traversal; preview retained promotions; move the full run to one new
quarantine child; verify source absence and quarantine contents; then delete
only that exact child. Never run recursive deletion directly against `90_temps/`
or any regular project root.
