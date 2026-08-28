[CmdletBinding()]
param(
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

function Get-NonCanonicalTrackedText {
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    $rows = & git -C $RepositoryRoot -c core.quotepath=false ls-files --eol
    if ($LASTEXITCODE -ne 0) {
        throw 'git ls-files --eol failed.'
    }

    foreach ($row in $rows) {
        if ($row -notmatch '^i/\S+\s+w/(?<work>\S+)\s+attr/(?<attributes>.*?)\t(?<path>.*)$') {
            continue
        }
        $workEnding = $Matches.work
        $attributes = $Matches.attributes
        $relativePath = $Matches.path
        if ($attributes -notmatch '(^|\s)eol=lf($|\s)') {
            continue
        }
        if ($workEnding -eq '-text') {
            continue
        }
        $path = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot $relativePath))
        $source = [IO.File]::ReadAllBytes($path)
        try {
            [void][Text.UTF8Encoding]::new($false, $true).GetString($source)
        } catch {
            [pscustomobject]@{ Problem = 'NON_UTF8'; Path = $relativePath }
            continue
        }
        if ($workEnding -in @('crlf', 'mixed', 'cr')) {
            [pscustomobject]@{ Problem = $workEnding.ToUpperInvariant(); Path = $relativePath }
            continue
        }
        if ($source.Length -gt 0 -and $source[$source.Length - 1] -ne 10) {
            [pscustomobject]@{ Problem = 'NO_FINAL_NEWLINE'; Path = $relativePath }
        }
    }
}

function Convert-TrackedTextToLf {
    param(
        [Parameter(Mandatory)][string]$RepositoryRoot,
        [Parameter(Mandatory)][string]$RelativePath
    )

    $rootPrefix = $RepositoryRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $path = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot $RelativePath))
    if (-not $path.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Tracked path escapes repository root: $RelativePath"
    }
    $item = Get-Item -LiteralPath $path
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to rewrite reparse-point path: $RelativePath"
    }

    $source = [IO.File]::ReadAllBytes($path)
    $result = [IO.MemoryStream]::new($source.Length)
    try {
        for ($index = 0; $index -lt $source.Length; $index++) {
            if ($source[$index] -eq 13) {
                if ($index + 1 -lt $source.Length -and $source[$index + 1] -eq 10) {
                    $index++
                }
                $result.WriteByte(10)
            } else {
                $result.WriteByte($source[$index])
            }
        }
        if ($result.Length -gt 0 -and $result.GetBuffer()[$result.Length - 1] -ne 10) {
            $result.WriteByte(10)
        }
        [IO.File]::WriteAllBytes($path, $result.ToArray())
    } finally {
        $result.Dispose()
    }
}

$repositoryRoot = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repositoryRoot)) {
    throw 'The text-format tool must run inside a Git worktree.'
}
$repositoryRoot = (Resolve-Path -LiteralPath $repositoryRoot).Path

$findings = @(Get-NonCanonicalTrackedText -RepositoryRoot $repositoryRoot)
if ($findings.Count -eq 0) {
    Write-Host 'text format: PASS (tracked LF policy files are canonical)'
    exit 0
}

if (-not $Apply) {
    $findings | Format-Table Problem, Path -AutoSize
    Write-Error "text format: FAIL ($($findings.Count) tracked file(s)); rerun with -Apply to normalize"
    exit 1
}

foreach ($finding in $findings) {
    if ($finding.Problem -eq 'NON_UTF8') {
        Write-Warning "refusing to guess source encoding for $($finding.Path)"
        continue
    }
    Convert-TrackedTextToLf -RepositoryRoot $repositoryRoot -RelativePath $finding.Path
    Write-Host "normalized $($finding.Path)"
}

$remaining = @(Get-NonCanonicalTrackedText -RepositoryRoot $repositoryRoot)
if ($remaining.Count -ne 0) {
    $remaining | Format-Table Problem, Path -AutoSize
    Write-Error "text format: FAIL ($($remaining.Count) tracked file(s) remain noncanonical)"
    exit 1
}

Write-Host "text format: PASS (normalized $($findings.Count) tracked file(s); changes are not staged)"
