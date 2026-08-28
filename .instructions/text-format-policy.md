# Text Format Policy

## Authority

- The repository-root `.gitattributes` is the byte-format authority for files
  checked out by Git. User, system, editor, and operating-system defaults do
  not override it.
- Authored and generated text uses UTF-8 with LF line endings and a final
  newline. True binary artifacts are marked `-text` and remain byte-preserved.
- `.editorconfig` aligns supporting editors with the Git policy. Language
  formatters and generators added by a fork must be configured to emit LF.
- Do not introduce extension-specific CRLF exceptions inside a Cell. Gate
  judges the observed bytes of all governed text in that Cell together.

## Verification and correction

Run the repository tool from any directory inside the worktree:

```powershell
pwsh -File 20_ops/tools/text-format.ps1
```

The check is read-only and exits nonzero when a tracked text file governed by
the LF attribute is CRLF or mixed. To rewrite only those tracked files without
staging them, run:

```powershell
pwsh -File 20_ops/tools/text-format.ps1 -Apply
```

Review the resulting diff and run the normal repository verification and
Comsect1 Gate afterward. `-Apply` is a byte-format correction only: it does not
add files, stage changes, change Git configuration, or touch files marked
`-text`.

Byte-addressed release payloads may be excluded only at their exact repository
path. A broad source-tree exception is not permitted.
