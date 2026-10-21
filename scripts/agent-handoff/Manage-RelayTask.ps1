[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Install', 'Stop', 'Status')][string]$Action,
    [string]$Job,
    [string]$Python,
    [Parameter(Mandatory = $true)][string]$StateDirectory,
    [ValidatePattern('^GremoVOD-AgentRelay-[A-Za-z0-9_-]+$')][string]$TaskName = 'GremoVOD-AgentRelay-Smoke',
    [switch]$Enable,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$controller = Join-Path $PSScriptRoot 'dispatcher.py'
$statePath = [IO.Path]::GetFullPath($StateDirectory)
if ($statePath.Contains('"')) { throw 'StateDirectory cannot contain quotes.' }
if ($Action -eq 'Stop') {
    # Write STOP before changing Scheduler: the live dispatcher terminates only its own children.
    if ($PSCmdlet.ShouldProcess($statePath, 'Stop relay and disable scheduled triggers')) {
        [IO.Directory]::CreateDirectory($statePath) | Out-Null
        [IO.File]::WriteAllText((Join-Path $statePath 'STOP'), [DateTime]::UtcNow.ToString('o'))
        Get-ScheduledTask -TaskName 'GremoVOD-AgentRelay-*' -ErrorAction SilentlyContinue |
            Where-Object { @($_.Actions | Where-Object {
                $_.Arguments.StartsWith(('"' + $controller + '"'), [StringComparison]::OrdinalIgnoreCase) -and
                $_.Arguments.IndexOf((' --state-dir "' + $statePath + '"'), [StringComparison]::OrdinalIgnoreCase) -ge 0
            }).Count -gt 0 } |
            ForEach-Object { Disable-ScheduledTask -InputObject $_ | Out-Null }
        Write-Output 'STOP requested. Future model calls are blocked; owned running children stop cooperatively.'
    }
    return
}
if ($Action -eq 'Status') {
    [pscustomobject]@{TaskName = $TaskName; StopMarker = (Test-Path -LiteralPath (Join-Path $statePath 'STOP'))}
    Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Select-Object TaskName, State
    return
}
if (-not $Job -or -not $Python) { throw 'Install requires absolute -Job and -Python paths.' }
$jobPath = (Resolve-Path -LiteralPath $Job).ProviderPath
$pythonPath = (Resolve-Path -LiteralPath $Python).ProviderPath
foreach ($checkedPath in @($controller, $jobPath, $pythonPath)) {
    if ($checkedPath.Contains('"')) { throw 'Paths containing quotes are not supported.' }
}
# This validates schema/scope without contacting GitHub or creating an approval.
& $pythonPath $controller --job $jobPath --validate-only
if ($LASTEXITCODE -ne 0) { throw 'Policy validation failed.' }
$policy = Get-Content -LiteralPath $jobPath -Raw -Encoding UTF8 | ConvertFrom-Json
$arguments = '"' + $controller + '" --job "' + $jobPath + '" --run --state-dir "' + $statePath + '"'
$timeLimit = [TimeSpan]::FromSeconds($policy.codex_timeout_seconds + $policy.minimax_timeout_seconds +
    2 * $policy.test_timeout_seconds * $policy.tests.Count + 120)
$plan = [pscustomobject]@{TaskName = $TaskName; Execute = $pythonPath; Arguments = $arguments;
    IntervalSeconds = 300; ExpiresAfterHours = 2; MultipleInstances = 'IgnoreNew'; Enabled = [bool]$Enable;
    LogonType = 'Interactive'; RunLevel = 'Limited'; TimeLimit = $timeLimit.ToString();
    Approval = 'Separate --arm owner approval required; no model calls during installation'}
$plan
if ($ValidateOnly) { return }
if ($PSCmdlet.ShouldProcess($TaskName, 'Register bounded dispatcher schedule (disabled unless -Enable)')) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        throw 'Task exists. Refusing to overwrite a task owned by another session.'
    }
    $scheduledAction = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory (Split-Path $controller -Parent)
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Hours 2)
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit $timeLimit -StartWhenAvailable
    $task = New-ScheduledTask -Action $scheduledAction -Trigger $trigger -Principal $principal -Settings $settings -Description 'GremoVOD bounded existing dispatcher; no merge, no production, explicit quota approval.'
    $task.Settings.Enabled = [bool]$Enable
    Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
    Write-Output 'Task registered. Owner approval remains independent from Scheduler enablement.'
}
