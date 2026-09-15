<#
.SYNOPSIS
    Local pre-merge checks for OptPLC (plan item P0-07, decision D-015).

.DESCRIPTION
    Runs the frontend type check, lint and tests, then the hermetic backend tests.
    Backend failures are compared with backend/app/tests/known_failures.txt, so the
    check fails only on NEW failures while the documented baseline is being fixed
    (see docs/plan/TEST_BASELINE.md). Dependency audits are report-only.

.PARAMETER Skip
    Step names to skip: typecheck, lint, frontend, backend, audit.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check.ps1 -Skip audit,lint
#>
param([string[]]$Skip = @())

$ErrorActionPreference = 'Continue'
# With -File, PowerShell passes "-Skip a,b" as one string, so split on commas here.
$Skip = @($Skip | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo 'backend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$knownFile = Join-Path $backend 'app\tests\known_failures.txt'
$results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Step, [string]$State, [int]$Seconds, [string]$Note = '') {
    $results.Add([pscustomobject]@{ Step = $Step; Result = $State; Seconds = $Seconds; Note = $Note })
}

# Each step body prints tool output through Out-Host and returns @{ Ok = <bool>; Note = <string> }.
function Invoke-Step([string]$Name, [string]$WorkDir, [scriptblock]$Body, [switch]$ReportOnly) {
    if ($Skip -contains $Name) {
        Add-Result $Name 'SKIPPED' 0
        return
    }
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    $start = Get-Date
    Push-Location $WorkDir
    try {
        $outcome = & $Body
    } catch {
        Write-Host $_ -ForegroundColor Red
        $outcome = @{ Ok = $false; Note = "exception: $($_.Exception.Message)" }
    } finally {
        Pop-Location
    }
    $seconds = [int]((Get-Date) - $start).TotalSeconds
    $state = if ($outcome.Ok) { 'PASS' } elseif ($ReportOnly) { 'WARN' } else { 'FAIL' }
    Add-Result $Name $state $seconds $outcome.Note
}

Invoke-Step 'typecheck' $repo {
    npx tsc --noEmit --incremental false | Out-Host
    @{ Ok = ($LASTEXITCODE -eq 0); Note = '' }
}

Invoke-Step 'lint' $repo {
    npm run lint --silent | Out-Host
    @{ Ok = ($LASTEXITCODE -eq 0); Note = '' }
}

Invoke-Step 'frontend' $repo {
    npx vitest run --reporter=dot | Out-Host
    @{ Ok = ($LASTEXITCODE -eq 0); Note = '' }
}

Invoke-Step 'backend' $backend {
    if (-not (Test-Path $python)) {
        return @{ Ok = $false; Note = "missing $python" }
    }
    $junit = Join-Path ([IO.Path]::GetTempPath()) ('optplc-junit-' + [guid]::NewGuid() + '.xml')
    & $python -m pytest -q -p no:cacheprovider "--junitxml=$junit" | Out-Host
    if (-not (Test-Path $junit)) {
        return @{ Ok = $false; Note = 'pytest produced no report' }
    }
    [xml]$report = Get-Content $junit -Raw
    Remove-Item $junit -Force

    $failed = @($report.SelectNodes('//testcase[failure or error]') |
        ForEach-Object { ($_.classname -replace '^app\.tests\.', '') + '::' + $_.name })
    $known = @()
    if (Test-Path $knownFile) {
        $known = @(Get-Content $knownFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') })
    }
    $new = @($failed | Where-Object { $known -notcontains $_ })
    $fixed = @($known | Where-Object { $failed -notcontains $_ })
    foreach ($test in $new) { Write-Host "  NEW FAILURE: $test" -ForegroundColor Red }
    foreach ($test in $fixed) { Write-Host "  Now passing, remove from known_failures.txt: $test" -ForegroundColor Yellow }

    $total = $report.SelectNodes('//testcase').Count
    $knownFailing = $failed.Count - $new.Count
    @{
        Ok = ($new.Count -eq 0)
        Note = "$total tests, $($failed.Count) failing ($($new.Count) new, $knownFailing known), $($fixed.Count) known now passing"
    }
}

Invoke-Step 'audit' $repo -ReportOnly {
    npm audit --omit=dev --audit-level=high | Out-Host
    $npmOk = ($LASTEXITCODE -eq 0)
    $npmNote = if ($npmOk) { 'npm clean' } else { 'npm findings' }
    & $python -m pip_audit --version *> $null
    if ($LASTEXITCODE -ne 0) {
        return @{ Ok = $false; Note = "$npmNote; pip-audit not installed" }
    }
    # Audit the hashed reference lock (P0-05): it is fully pinned, so pip-audit needs no temporary venv.
    # The Windows system proxy on this machine is SOCKS, which requests cannot use without PySocks,
    # and PyPI is reachable directly, so proxies are bypassed for this call only (D-027).
    $savedNoProxy = $env:NO_PROXY
    $env:NO_PROXY = '*'
    try {
        & $python -m pip_audit --progress-spinner off --disable-pip -r (Join-Path $backend 'requirements-docker.lock') | Out-Host
        $pipOk = ($LASTEXITCODE -eq 0)
    } finally {
        $env:NO_PROXY = $savedNoProxy
    }
    $pipNote = if ($pipOk) { 'pip-audit clean' } else { 'pip-audit findings' }
    @{ Ok = ($npmOk -and $pipOk); Note = "$npmNote; $pipNote" }
}

Write-Host "`n==> Summary" -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-Host
if (@($results | Where-Object { $_.Result -eq 'FAIL' }).Count -gt 0) {
    Write-Host 'CHECK FAILED' -ForegroundColor Red
    exit 1
}
Write-Host 'CHECK PASSED' -ForegroundColor Green
exit 0
