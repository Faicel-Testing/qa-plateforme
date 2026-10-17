$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$lock=Join-Path $root 'logs/gateway/quota.lock'
if(!(Test-Path -LiteralPath $lock)){Write-Output 'No quota lock to recover';exit}
$item=Get-Item -LiteralPath $lock
if(((Get-Date)-$item.LastWriteTime).TotalHours -lt 1){throw 'Recent lock; recovery refused'}
$nodes=@(Get-Process node -ErrorAction SilentlyContinue)
foreach($node in $nodes){if(!$node.StartTime -or $node.StartTime -le $item.LastWriteTime){throw 'A Node process may own this lock; recovery refused'}}
$again=Get-Item -LiteralPath $lock
if($again.LastWriteTimeUtc -ne $item.LastWriteTimeUtc -or $again.Length -ne $item.Length){throw 'Lock changed; recovery refused'}
$destination=$lock+'.recovered-'+[guid]::NewGuid().ToString()
Move-Item -LiteralPath $lock -Destination $destination
Write-Output 'Abandoned quota lock archived; quota ledger preserved.'
