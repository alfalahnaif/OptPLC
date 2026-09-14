<#
.SYNOPSIS
    Compile one IEC 61131-3 Structured Text file with the pinned MATIEC in the reference image (plan item P0-06).

.DESCRIPTION
    Runs iec2c inside the OptPLC reference image as the unprivileged app user, with no network,
    the source mounted read-only, and generated C written to a throwaway directory inside the
    container. The source is compiled exactly as written: no normalization is applied.
    Prints the raw compiler output and exits with iec2c's return code.

    The file is copied to a private temporary folder under the fixed name input.st, so neither the
    path nor quoting ever reaches the container shell (Windows PowerShell 5.1 mangles embedded
    double quotes in native arguments).

.PARAMETER Path
    Structured Text file to compile.

.PARAMETER Image
    Reference image tag built from docker/app.Dockerfile.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\st-compile.ps1 -Path examples\motor.st
#>
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$Image = 'optplc-backend:p0-05'
)

$ErrorActionPreference = 'Continue'
if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    Write-Host "File not found: $Path" -ForegroundColor Red
    exit 2
}
docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Image not found: $Image. Build it with: docker build -f docker/app.Dockerfile -t $Image ." -ForegroundColor Red
    exit 2
}

$file = (Resolve-Path -LiteralPath $Path).Path
$name = Split-Path -Leaf $file
$work = Join-Path ([IO.Path]::GetTempPath()) ('optplc-st-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $work | Out-Null
Copy-Item -LiteralPath $file -Destination (Join-Path $work 'input.st')

try {
    $compile = 'mkdir -p /tmp/iec2c-out && cd /usr/local/share/matiec && echo matiec commit: $(cat COMMIT) && iec2c -I lib -T /tmp/iec2c-out /src/input.st'
    docker run --rm --network none -v "${work}:/src:ro" --entrypoint sh $Image -c $compile
    $code = $LASTEXITCODE
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force
}

if ($code -eq 0) {
    Write-Host "iec2c: OK ($name)" -ForegroundColor Green
} else {
    Write-Host "iec2c: FAILED with exit code $code ($name)" -ForegroundColor Red
}
exit $code
