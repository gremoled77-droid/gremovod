<#
.SYNOPSIS
    Health check for the Aider + MiniMax M3.1 Flash setup in GremoVOD.

.DESCRIPTION
    Checks, in order, that the whole chain is alive:
      1. tool versions (aider, git, python)
      2. the DPAPI key store exists and decrypts (the value is never printed)
      3. the MiniMax API accepts the key (one tiny request, ~0.00001 USD)
      4. the launcher resolves the GremoVOD repository
      5. Aider builds the repository map offline (no API cost)
      6. optional: the full backend test suite

    Prints a green/red line per check and exits non-zero if anything is red.

.EXAMPLE
    .\scripts\aider\Test-AiderSetup.ps1

.EXAMPLE
    .\scripts\aider\Test-AiderSetup.ps1 -SkipApi -SkipTests
#>
[CmdletBinding()]
param(
    [string]$RepoPath = 'C:\AI_Workflow_Studio',
    [string]$StorePath = (Join-Path $env:USERPROFILE '.minimax\credentials\minimax-mplan.key'),
    [string]$ApiBase = 'https://api.minimax.io/v1',
    [string]$Model = 'MiniMax-M3.1-Flash',

    # Skip the live API call (the only check that spends money).
    [switch]$SkipApi,

    # Skip the backend test suite (takes ~70-110 s).
    [switch]$SkipTests
)

$ErrorActionPreference = 'Continue'
$script:failed = 0

function Write-Check {
    param([string]$Name, [bool]$Ok, [string]$Detail = '')
    if ($Ok) {
        Write-Host ('  [ OK ] ' + $Name) -ForegroundColor Green
        if ($Detail) { Write-Host ('         ' + $Detail) -ForegroundColor DarkGray }
    }
    else {
        Write-Host ('  [FAIL] ' + $Name) -ForegroundColor Red
        if ($Detail) { Write-Host ('         ' + $Detail) -ForegroundColor Red }
        $script:failed++
    }
}

Write-Host ''
Write-Host '=== Aider + MiniMax M3.1 Flash: проверка готовности ===' -ForegroundColor Cyan
Write-Host ''

Write-Host '[1] Инструменты' -ForegroundColor Cyan
$aiderVersion = ((& aider --version 2>&1) -join ' ').Trim()
Write-Check 'aider установлен' ([bool]$aiderVersion) $aiderVersion
Write-Check 'git доступен' ([bool](Get-Command git -ErrorAction SilentlyContinue)) (git --version 2>&1)
Write-Check 'python доступен' ([bool](Get-Command python -ErrorAction SilentlyContinue)) (python --version 2>&1)

Write-Host ''
Write-Host '[2] Ключ MiniMax (значение не выводится)' -ForegroundColor Cyan
$key = $null
if (-not (Test-Path $StorePath)) {
    Write-Check 'хранилище DPAPI найдено' $false ('нет файла: ' + $StorePath)
}
else {
    Write-Check 'хранилище DPAPI найдено' $true ($StorePath + ' (' + (Get-Item $StorePath).Length + ' байт шифротекста)')
    try {
        Add-Type -AssemblyName System.Security
        $enc = [IO.File]::ReadAllBytes($StorePath)
        $plain = [Security.Cryptography.ProtectedData]::Unprotect(
            $enc, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        $key = [Text.Encoding]::UTF8.GetString($plain)
        [Array]::Clear($plain, 0, $plain.Length)
        Write-Check 'ключ расшифровывается' ($key.Length -gt 20) ('длина ' + $key.Length + ' симв.')
    }
    catch {
        Write-Check 'ключ расшифровывается' $false $_.Exception.Message
    }
}

Write-Host ''
Write-Host '[3] Авторизация в API MiniMax' -ForegroundColor Cyan
if ($SkipApi) {
    Write-Check 'проверка API' $true 'пропущена (-SkipApi)'
}
elseif (-not $key) {
    Write-Check 'авторизация API' $false 'нет ключа'
}
else {
    $headers = @{ 'Authorization' = ('Bearer ' + $key); 'Content-Type' = 'application/json' }
    $body = @{
        model = $Model; messages = @(@{ role = 'user'; content = 'ping' })
        max_tokens = 16; reasoning_effort = 'low'; stream = $false
    } | ConvertTo-Json -Depth 6
    try {
        $r = Invoke-WebRequest -Uri ($ApiBase.TrimEnd('/') + '/chat/completions') -Method Post `
            -Headers $headers -Body $body -ContentType 'application/json' -TimeoutSec 90 -UseBasicParsing
        $j = $r.Content | ConvertFrom-Json
        Write-Check 'авторизация API' ($r.StatusCode -eq 200) ('HTTP ' + $r.StatusCode + ', model=' + $j.model + ', ответ=' + $j.choices[0].message.content)
    }
    catch {
        Write-Check 'авторизация API' $false $_.Exception.Message
    }
}
$key = $null

Write-Host ''
Write-Host '[4] Лаунчер находит репозиторий' -ForegroundColor Cyan
$launcher = Join-Path $PSScriptRoot 'Start-AiderGremoVOD.ps1'
if (-not (Test-Path $launcher)) {
    Write-Check 'лаунчер на месте' $false ('нет файла: ' + $launcher)
}
else {
    Write-Check 'лаунчер на месте' $true $launcher
    # 6>&1 captures the Write-Host information stream, 2>&1 the stderr.
    $printed = (& $launcher -RepoPath $RepoPath -PrintCommand 6>&1 2>&1 | Out-String)
    $hasRepo = $printed -match [regex]::Escape($RepoPath)
    $hasModel = $printed -match 'openai/MiniMax-M3\.1-Flash'
    Write-Check 'корень и модель определены' ($hasRepo -and $hasModel) (
        (($printed -split "`n") | Where-Object { $_ -match 'Repo\s+:|Model\s+:' } | ForEach-Object { $_.Trim() }) -join '; ')
}

Write-Host ''
Write-Host '[5] Карта репозитория строится (без обращения к API)' -ForegroundColor Cyan
$metadata = Join-Path $PSScriptRoot 'aider-minimax.model.metadata.json'
$mapArgs = @(
    '--show-repo-map', '--model', 'openai/MiniMax-M3.1-Flash', '--map-tokens', '2048',
    '--no-auto-commits', '--no-dirty-commits', '--no-show-model-warnings', '--no-check-update'
)
if (Test-Path $metadata) { $mapArgs += @('--model-metadata-file', $metadata) }
Push-Location $RepoPath
$mapOut = (& aider @mapArgs 2>&1 | Out-String)
Pop-Location
$filesFound = [regex]::Match($mapOut, 'with (\d+) files')
Write-Check 'Aider видит файлы GremoVOD' $filesFound.Success ($filesFound.Groups[1].Value + ' файлов в репозитории')
Write-Check 'карта построена' ($mapOut -match 'Repo-map: using 2048 tokens') 'Repo-map: using 2048 tokens'

Write-Host ''
Write-Host '[6] Набор серверных тестов' -ForegroundColor Cyan
if ($SkipTests) {
    Write-Check 'тесты бэкенда' $true 'пропущены (-SkipTests)'
}
else {
    $py = Join-Path $RepoPath '.venv\Scripts\python.exe'
    if (-not (Test-Path $py)) { $py = 'python' }
    Push-Location $RepoPath
    $out = (& $py -X utf8 -m unittest discover -s backend -p 'test_*.py' 2>&1 | Out-String)
    $code = $LASTEXITCODE
    Pop-Location
    $ran = [regex]::Match($out, 'Ran (\d+) tests')
    Write-Check 'тесты бэкенда' ($code -eq 0) ($ran.Groups[1].Value + ' тестов, exit ' + $code)
}

Write-Host ''
if ($script:failed -eq 0) {
    Write-Host 'ИТОГ: всё зелёное — связка готова к работе.' -ForegroundColor Green
    Write-Host 'Запуск Aider:  .\scripts\aider\Start-AiderGremoVOD.ps1' -ForegroundColor Cyan
    exit 0
}
else {
    Write-Host ('ИТОГ: провалено проверок: ' + $script:failed) -ForegroundColor Red
    exit 1
}
