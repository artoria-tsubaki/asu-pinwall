param(
    [string]$InputPath = 'bilibili_space_1634470651_uploads.json'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Get-DescHtml {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    $headers = @{
        'User-Agent'      = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        'Accept-Language' = 'zh-CN,zh;q=0.9'
        'Referer'         = 'https://www.bilibili.com/'
    }

    $response = Invoke-WebRequest -Uri $Url -Headers $headers -TimeoutSec 30
    $html = $response.Content

    $match = [regex]::Match(
        $html,
        '(?is)<(?:span|div)\b[^>]*class="[^"]*\bdesc-info-text\b[^"]*"[^>]*>(?<content>.*?)</(?:span|div)>'
    )

    if (-not $match.Success) {
        throw "desc-info-text not found: $Url"
    }

    $content = $match.Groups['content'].Value.Trim()
    if ([string]::IsNullOrWhiteSpace($content)) {
        return ''
    }

    $containsHtmlTag = [regex]::IsMatch($content, '(?is)<[a-z!/][^>]*>')
    if ($containsHtmlTag) {
        return $content
    }

    $decoded = [System.Net.WebUtility]::HtmlDecode($content)
    $decoded = $decoded -replace "`r`n?", "`n"
    $decoded = $decoded.Replace([char]0x00A0, ' ')

    $lines = $decoded -split "`n" |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -ne '' }

    if ($lines.Count -eq 0) {
        return ''
    }

    $paragraphs = foreach ($line in $lines) {
        '<p>{0}</p>' -f [System.Net.WebUtility]::HtmlEncode($line)
    }

    return ($paragraphs -join '')
}

$resolvedPath = Resolve-Path -LiteralPath $InputPath
$items = Get-Content -LiteralPath $resolvedPath -Raw -Encoding UTF8 | ConvertFrom-Json

$total = @($items).Count
$index = 0

foreach ($item in $items) {
    $index += 1
    $url = $item.media.url

    try {
        $descHtml = Get-DescHtml -Url $url
        $item.text.text = $descHtml
        Write-Host ("[{0}/{1}] OK  {2}" -f $index, $total, $url)
    } catch {
        Write-Warning ("[{0}/{1}] FAIL {2} :: {3}" -f $index, $total, $url, $_.Exception.Message)
    }

    Start-Sleep -Milliseconds 300
}

$json = $items | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($resolvedPath.Path, $json, [System.Text.UTF8Encoding]::new($false))
