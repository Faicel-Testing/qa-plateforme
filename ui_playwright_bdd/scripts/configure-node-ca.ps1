$file=Join-Path (Split-Path $PSScriptRoot -Parent) '.env'
$content=[IO.File]::ReadAllText($file)
$line='NODE_EXTRA_CA_CERTS=logs/plane/windows-ca.pem'
if($content -match '(?m)^NODE_EXTRA_CA_CERTS='){$content=[regex]::Replace($content,'(?m)^NODE_EXTRA_CA_CERTS=.*$',$line)}else{$content+="`r`n"+$line+"`r`n"}
[IO.File]::WriteAllText($file,$content,[Text.UTF8Encoding]::new($false))
Write-Output 'Trusted certificate bundle configured for Node child processes.'
