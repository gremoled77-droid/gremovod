param(
    [ValidateSet('check', 'credits')]
    [string]$Action = 'check'
)
. (Join-Path $PSScriptRoot 'common.ps1')
$pointer = [IntPtr]::Zero
try {
    $key = $env:KIE_API_KEY
    if ([string]::IsNullOrWhiteSpace($key)) {
        $keyPath = Join-Path $PSScriptRoot 'api-key.dpapi'
        if (-not (Test-Path -LiteralPath $keyPath)) { throw 'Run kie-access\connect.ps1 first, or set KIE_API_KEY.' }
        $secret = ConvertTo-SecureString -String ((Get-Content -LiteralPath $keyPath -Raw).Trim())
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
        $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    $response = Invoke-KieCredit $key
    if ($Action -eq 'credits') { $response | ConvertTo-Json -Depth 10 }
    else { Write-Host "KIE access verified. Credits: $($response.data)." }
} finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $key = $null
    $secret = $null
}
