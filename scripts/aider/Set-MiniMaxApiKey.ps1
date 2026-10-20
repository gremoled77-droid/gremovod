<#
.SYNOPSIS
    Securely stores the MiniMax M Plan Subscription Key for Aider.

.DESCRIPTION
    Reads the key with a masked prompt (nothing is echoed, nothing is typed into a
    shell history), validates it against the MiniMax OpenAI-compatible API, then
    encrypts it with Windows DPAPI (CurrentUser scope) and writes it to a file
    OUTSIDE the Git repository.

    The plain-text key only exists in this process' memory. It is never written
    to the repository, to .aider.conf.yml, to logs or to the console.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\aider\Set-MiniMaxApiKey.ps1

.EXAMPLE
    # Non-interactive: reuse a key that is already in the environment
    powershell -ExecutionPolicy Bypass -File .\scripts\aider\Set-MiniMaxApiKey.ps1 -FromEnvironment
#>
[CmdletBinding()]
param(
    # Where the DPAPI-encrypted blob is stored. Outside the repository by default.
    [string]$StorePath = (Join-Path $env:USERPROFILE '.minimax\credentials\minimax-mplan.key'),

    [string]$ApiBase = 'https://api.minimax.io/v1',

    [string]$Model = 'MiniMax-M3.1-Flash',

    # Use a key that is already present in the environment instead of prompting.
    [switch]$FromEnvironment,

    # Store the key without contacting the API.
    [switch]$SkipValidate
)

$ErrorActionPreference = 'Stop'

function ConvertTo-PlainText {
    param([Security.SecureString]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Test-MiniMaxKey {
    param(
        [string]$Key,
        [string]$ApiBase,
        [string]$Model
    )
    $uri = $ApiBase.TrimEnd('/') + '/chat/completions'
    $headers = @{ 'Authorization' = "Bearer $Key"; 'Content-Type' = 'application/json' }
    $body = @{
        model           = $Model
        messages        = @(@{ role = 'user'; content = 'ping' })
        max_tokens      = 16
        reasoning_effort = 'low'
        stream          = $false
    } | ConvertTo-Json -Depth 6

    try {
        $resp = Invoke-WebRequest -Uri $uri -Method Post -Headers $headers -Body $body `
            -ContentType 'application/json' -TimeoutSec 60 -UseBasicParsing
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
            return @{ ok = $true; detail = "HTTP $($resp.StatusCode)" }
        }
        return @{ ok = $false; detail = "HTTP $($resp.StatusCode)" }
    }
    catch {
        $msg = $_.Exception.Message
        $status = $null
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        if ($status) {
            return @{ ok = $false; detail = "HTTP $status : $msg" }
        }
        return @{ ok = $false; detail = $msg }
    }
}

Write-Host '=== MiniMax M Plan Subscription Key ===' -ForegroundColor Cyan
Write-Host "Store : $StorePath"
Write-Host "API   : $ApiBase"
Write-Host "Model : $Model"
Write-Host ''

$key = $null
if ($FromEnvironment) {
    foreach ($name in @('MINIMAX_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY')) {
        $v = [Environment]::GetEnvironmentVariable($name)
        if ($v) { $key = $v; Write-Host "Using key from environment variable $name." -ForegroundColor Green; break }
    }
    if (-not $key) {
        Write-Error 'No key found in MINIMAX_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY.'
        exit 2
    }
}
else {
    Write-Host 'Paste the Subscription Key from https://platform.minimax.io/console/plan' -ForegroundColor Yellow
    Write-Host 'Input is masked; nothing is echoed and nothing is written to shell history.'
    $secure = Read-Host -Prompt 'MiniMax Subscription Key' -AsSecureString
    if (-not $secure -or $secure.Length -eq 0) {
        Write-Error 'Empty key.'
        exit 2
    }
    $key = ConvertTo-PlainText -Secure $secure
}

if (-not $SkipValidate) {
    Write-Host 'Validating against the MiniMax API ...' -ForegroundColor Cyan
    $check = Test-MiniMaxKey -Key $key -ApiBase $ApiBase -Model $Model
    if (-not $check.ok) {
        Write-Host "Authentication FAILED: $($check.detail)" -ForegroundColor Red
        Write-Host 'Key was NOT saved.' -ForegroundColor Red
        exit 3
    }
    Write-Host "API authentication successful ($($check.detail))" -ForegroundColor Green
}
else {
    Write-Host 'Validation skipped.' -ForegroundColor Yellow
}

Add-Type -AssemblyName System.Security
$plainBytes = [Text.Encoding]::UTF8.GetBytes($key)
$protected = [Security.Cryptography.ProtectedData]::Protect(
    $plainBytes,
    $null,
    [Security.Cryptography.DataProtectionScope]::CurrentUser
)
[Array]::Clear($plainBytes, 0, $plainBytes.Length)

$dir = Split-Path -Parent $StorePath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
[IO.File]::WriteAllBytes($StorePath, $protected)

Write-Host "Saved encrypted key (DPAPI, CurrentUser) to: $StorePath" -ForegroundColor Green
Write-Host "File size: $((Get-Item $StorePath).Length) bytes (ciphertext)." -ForegroundColor DarkGray
Write-Host 'Launch Aider with:  .\scripts\aider\Start-AiderGremoVOD.ps1' -ForegroundColor Cyan
exit 0
