<#
.SYNOPSIS
    Launches Aider for GremoVOD with the MiniMax M3.1 Flash model.

.DESCRIPTION
    Reads the DPAPI-encrypted MiniMax Subscription Key from the local credential
    store, exposes it to the Aider process as OPENAI_API_KEY / OPENAI_API_BASE
    (process-local environment only), and starts Aider with the project settings:

        --model / --weak-model  openai/MiniMax-M3.1-Flash
        --openai-api-base       https://api.minimax.io/v1
        --map-tokens            2048
        --no-auto-commits       Aider never commits on its own
        --no-dirty-commits      Aider never commits a dirty tree
        --edit-format           diff
        --no-cache-prompts      no paid prompt-cache keepalive

    The key is never printed, never written to the repository and never pushed.

.EXAMPLE
    .\scripts\aider\Start-AiderGremoVOD.ps1

.EXAMPLE
    # One-shot question, no interactive chat
    .\scripts\aider\Start-AiderGremoVOD.ps1 -AiderArgs @('--message','Which files implement the camera catalog?')

.EXAMPLE
    # Run against a specific checkout
    .\scripts\aider\Start-AiderGremoVOD.ps1 -RepoPath C:\AI_Workflow_Studio\.worktrees\aider-minimax
#>
[CmdletBinding()]
param(
    # Repository checkout Aider should work in. Defaults to the Git root of this script.
    [string]$RepoPath,

    # Extra arguments forwarded to Aider.
    [string[]]$AiderArgs = @(),

    [string]$ApiBase = 'https://api.minimax.io/v1',

    [string]$Model = 'openai/MiniMax-M3.1-Flash',

    [string]$WeakModel = 'openai/MiniMax-M3.1-Flash',

    [int]$MapTokens = 2048,

    # Location of the DPAPI-encrypted MiniMax key.
    [string]$StorePath = (Join-Path $env:USERPROFILE '.minimax\credentials\minimax-mplan.key'),

    # Print the effective command and exit without starting Aider.
    [switch]$PrintCommand
)

$ErrorActionPreference = 'Stop'

# --- resolve the repository -------------------------------------------------
function Resolve-GitRoot {
    param([string]$StartPath)
    if (-not $StartPath) { return $null }
    if (-not (Test-Path $StartPath)) { return $null }
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # git writes "fatal: not a git repository" to stderr; swallow it instead of
        # letting ErrorActionPreference=Stop turn it into a terminating error.
        $out = (& git -C $StartPath rev-parse --show-toplevel 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $out) {
            if (Test-Path (Join-Path $out '.git')) { return $out }
        }
    }
    catch { }
    finally { $ErrorActionPreference = $old }
    return $null
}

if (-not $RepoPath) { $RepoPath = $env:GREMOVOD_ROOT }

if (-not $RepoPath) {
    # 1) the script itself lives inside a repository or worktree
    $RepoPath = Resolve-GitRoot -StartPath $PSScriptRoot
}

if (-not $RepoPath) {
    # 2) the current directory is a repository (daily use from the GremoVOD root)
    $RepoPath = Resolve-GitRoot -StartPath (Get-Location).Path
}

if (-not $RepoPath) {
    Write-Host 'Could not locate the GremoVOD repository.' -ForegroundColor Red
    Write-Host "Tried: script folder '$PSScriptRoot' and current folder '$((Get-Location).Path)'." -ForegroundColor Red
    Write-Host 'Run it from the GremoVOD root, or pass -RepoPath <path>,' -ForegroundColor Yellow
    Write-Host 'or set GREMOVOD_ROOT to the repository path.' -ForegroundColor Yellow
    exit 2
}

$RepoPath = (Resolve-Path $RepoPath).Path
if (-not (Test-Path (Join-Path $RepoPath '.git'))) {
    Write-Error "Not a Git repository: $RepoPath"
    exit 2
}

$metadata = Join-Path $PSScriptRoot 'aider-minimax.model.metadata.json'
if (-not (Test-Path $metadata)) { $metadata = $null }

# --- build the command ------------------------------------------------------
$cmdArgs = @(
    '--model', $Model,
    '--weak-model', $WeakModel,
    '--openai-api-base', $ApiBase,
    '--map-tokens', "$MapTokens",
    '--no-auto-commits',
    '--no-dirty-commits',
    '--no-cache-prompts',
    '--cache-keepalive-pings', '0',
    '--edit-format', 'diff'
)
if ($metadata) { $cmdArgs += @('--model-metadata-file', $metadata) }
$cmdArgs += $AiderArgs

Write-Host '=== Aider / MiniMax M3.1 Flash ===' -ForegroundColor Cyan
Write-Host "Repo    : $RepoPath"
Write-Host "Model   : $Model"
Write-Host "API base: $ApiBase"
Write-Host "Command : aider $($cmdArgs -join ' ')"
Write-Host ''

if ($PrintCommand) { exit 0 }

# --- load the key -----------------------------------------------------------
function Get-MiniMaxKey {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    Add-Type -AssemblyName System.Security
    $enc = [IO.File]::ReadAllBytes($Path)
    $plain = [Security.Cryptography.ProtectedData]::Unprotect(
        $enc, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    $s = [Text.Encoding]::UTF8.GetString($plain)
    [Array]::Clear($plain, 0, $plain.Length)
    return $s
}

$key = Get-MiniMaxKey -Path $StorePath
if (-not $key) {
    if ($env:OPENAI_API_KEY) {
        $key = $env:OPENAI_API_KEY
        Write-Host 'Using OPENAI_API_KEY from the environment.' -ForegroundColor DarkGray
    }
    else {
        Write-Host 'No MiniMax key found.' -ForegroundColor Red
        Write-Host "Expected DPAPI store: $StorePath" -ForegroundColor Red
        Write-Host 'Create it with:  .\scripts\aider\Set-MiniMaxApiKey.ps1' -ForegroundColor Yellow
        exit 3
    }
}
Write-Host 'Key     : loaded (not shown)' -ForegroundColor DarkGray

# Process-local only: never written to disk, never to Git.
$env:OPENAI_API_KEY = $key
$env:OPENAI_API_BASE = $ApiBase
$env:AIDER_OPENAI_API_BASE = $ApiBase

# Windows consoles with a legacy code page (cp1251) make Aider crash with
# UnicodeEncodeError while printing the repo map. Force UTF-8 for the child.
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

Push-Location $RepoPath
try {
    # Aider writes progress to stderr; with ErrorActionPreference=Stop that would
    # abort the script, so relax it around the native call.
    $ErrorActionPreference = 'Continue'
    & aider @cmdArgs
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    exit $code
}
finally {
    Pop-Location
    $env:OPENAI_API_KEY = $null
    $env:OPENAI_API_BASE = $null
    $env:AIDER_OPENAI_API_BASE = $null
    $key = $null
}
