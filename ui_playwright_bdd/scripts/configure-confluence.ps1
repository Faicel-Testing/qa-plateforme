$ErrorActionPreference='Stop'
if (!$env:CONFLUENCE_EMAIL -or !$env:CONFLUENCE_API_TOKEN) {throw 'Credentials required in process environment'}
$file=Join-Path (Split-Path $PSScriptRoot -Parent) '.env'
$content=[IO.File]::ReadAllText($file)
$settings=@{CONFLUENCE_EMAIL=$env:CONFLUENCE_EMAIL;CONFLUENCE_API_TOKEN=$env:CONFLUENCE_API_TOKEN;CONFLUENCE_RAG_ENABLED='true';CONFLUENCE_CA_FILE='logs/plane/windows-ca.pem'}
foreach($name in $settings.Keys){
 $pattern='(?m)^'+$name+'=.*$'
 $line=$name+'='+$settings[$name]
 if([regex]::IsMatch($content,$pattern)){$content=[regex]::Replace($content,$pattern,[Text.RegularExpressions.MatchEvaluator]{param($match) $line})}else{$content+="`r`n"+$line}
}
[IO.File]::WriteAllText($file,$content+"`r`n",[Text.UTF8Encoding]::new($false))
Write-Output 'Confluence credentials configured locally; automatic RAG refresh enabled.'
