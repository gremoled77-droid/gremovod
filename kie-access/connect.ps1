param([string]$KeyFile = '')
. (Join-Path $PSScriptRoot 'common.ps1')
if ($KeyFile) {
    $secret = ConvertTo-SecureString -String ((Get-Content -LiteralPath $KeyFile -Raw).Trim()) -AsPlainText -Force
} else {
    $secret = Read-Host 'Paste KIE API key (input is hidden)' -AsSecureString
}
$pointer = [IntPtr]::Zero
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim()
    if ([string]::IsNullOrWhiteSpace($key)) { throw 'API key is empty.' }
    $response = Invoke-KieCredit $key
    $key | ConvertTo-SecureString -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'api-key.dpapi')
    Write-Host "KIE access verified. Credits: $($response.data). Key encrypted for the current Windows user."
} finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $key = $null
    $secret = $null
}
