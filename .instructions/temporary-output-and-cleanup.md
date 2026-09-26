# Temporary Output and Cleanup

Use only these disposable roots:

```text
90_temps/build/<tool>/<run-id>/
90_temps/verification/<tool>/<run-id>/
90_temps/validation/<tool>/<run-id>/
90_temps/generation/<tool>/<run-id>/
90_temps/release/<tool>/<run-id>/
90_temps/scratch/<tool>/<run-id>/
90_temps/development/<tool>/<scope>/
99_trash/<cleanup-id>/
```

The `development` path is the sole reusable-cache exception. A fork's
language-specific instructions must name its exact `<tool>/<scope>` child and
the command that uses it. It is operational output, never evidence. All other
paths are task-owned runs and must remain non-overlapping.

For cleanup, close producers; enumerate the exact task-owned run; resolve and
validate source and destination; reject aliases, links, mounts, junctions, and
reparse traversal; preview retained promotions; move the full run to one new
quarantine child; verify source absence and quarantine contents; then delete
only that exact child. Never run recursive deletion directly against `90_temps/`
or any regular project root.
