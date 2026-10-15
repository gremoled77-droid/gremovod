param(
    [Parameter(Mandatory=$true)][string]$Path,
    [ValidateSet('Get','Post')][string]$Method = 'Get',
    [string]$BodyFile = '',
    [string]$OutputFile = '',
    [switch]$Upload
)
$ErrorActionPreference = 'Stop'
if (-not $Path.StartsWith('/api/')) { throw 'Only /api/ paths are allowed.' }
$secret = ConvertTo-SecureString -String ((Get-Content -LiteralPath (Join-Path $PSScriptRoot 'api-key.dpapi') -Raw).Trim())
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $hostUrl = 'https://api.kie.ai'
    if ($Upload) { $hostUrl = 'https://kieai.redpandaai.co' }
    $params = @{ Method = $Method; Uri = $hostUrl + $Path; Headers = @{ Authorization = 'Bearer ' + $key }; TimeoutSec = 120; MaximumRedirection = 0 }
    if ($BodyFile) { $params.Body = [Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText((Resolve-Path -LiteralPath $BodyFile))); $params.ContentType = 'application/json' }
    try { $result = Invoke-RestMethod @params } catch {
        $status = 'network error'
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        throw "KIE HTTP request failed ($status); credentials suppressed."
    }
    if ($result.code -ne 200) { throw "KIE API error $($result.code): $($result.msg)" }
    $json = $result | ConvertTo-Json -Depth 100
    if ($OutputFile) { [IO.File]::WriteAllText($OutputFile, $json) } else { $json }
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $key = $null
    $secret = $null
}
