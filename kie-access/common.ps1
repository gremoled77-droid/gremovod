$ErrorActionPreference = 'Stop'

function Invoke-KieCredit([string]$Key) {
    try {
        $response = Invoke-RestMethod -Method Get -Uri 'https://api.kie.ai/api/v1/chat/credit' -Headers @{ Authorization = 'Bearer ' + $Key } -TimeoutSec 30 -MaximumRedirection 0
    } catch {
        $status = 'network error'
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        throw "KIE request failed ($status). Check API key, IP whitelist, and network access."
    }
    # KIE may return HTTP 200 with an API error code in the JSON body.
    if ($null -eq $response -or $response.code -ne 200 -or $null -eq $response.data) {
        throw "KIE credit check failed (API code: $($response.code)). Check key, permissions, and rate limits."
    }
    return $response
}
