param([string]$SpaceId, [switch]$Apply)
$ErrorActionPreference = 'Stop'
$base = 'https://faicelganem-1791143297915.atlassian.net/wiki'
if (!$env:CONFLUENCE_API_TOKEN -or !$env:CONFLUENCE_EMAIL) { throw 'Confluence credentials missing' }
$headers = @{ Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($env:CONFLUENCE_EMAIL + ':' + $env:CONFLUENCE_API_TOKEN)); Accept='application/json' }
function Request([string]$route, [string]$method='GET', $body=$null) {
  $opts = @{Uri=($base + '/api/v2/' + $route);Method=$method;Headers=$headers;TimeoutSec=30;MaximumRedirection=0}
  if ($null -ne $body) { $opts.ContentType='application/json; charset=utf-8'; $opts.Body=[Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 15 -Compress)) }
  try { Invoke-RestMethod @opts } catch { if ($_.Exception.Response) { throw ('Confluence HTTP ' + [int]$_.Exception.Response.StatusCode) }; throw 'Confluence network request failed' }
}
if (!$Apply) {
  $next='spaces?limit=100'
  do {
    $data=Request $next
    $data.results | Select-Object id,key,name,type,homepageId | ConvertTo-Json -Depth 5
    $next=$null
    if ($data._links.next) { $uri=[uri]::new([uri]$base,$data._links.next); if ($uri.Host -ne ([uri]$base).Host -or !$uri.AbsolutePath.StartsWith('/wiki/api/v2/')) {throw 'Unexpected pagination URL'}; $next=$uri.PathAndQuery.Substring('/wiki/api/v2/'.Length) }
  } while ($next)
  exit
}
if ($SpaceId -notmatch '^\d+$') { throw 'SpaceId required' }
$root=Split-Path $PSScriptRoot -Parent
$payload=Get-Content (Join-Path $root 'logs/confluence/spec-payload.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$found=Request ('pages?space-id='+$SpaceId+'&title='+[uri]::EscapeDataString($payload.title))
if ($found.results.Count -gt 0) { throw 'Page title already exists; refusing to overwrite existing content' }
$created=Request 'pages' 'POST' @{spaceId=$SpaceId;status='current';title=$payload.title;body=@{representation='storage';value=$payload.html}}
$saved=Request ('pages/'+$created.id+'?body-format=storage')
foreach ($marker in $payload.markers) { if (!$saved.body.storage.value.Contains($marker)) { throw 'Published content verification failed' } }
$report=@{id=$saved.id;title=$saved.title;url=($base+'/pages/viewpage.action?pageId='+$saved.id);verified=$true}
$report | ConvertTo-Json | Set-Content (Join-Path $root 'logs/confluence/published.json') -Encoding UTF8
$report | ConvertTo-Json
