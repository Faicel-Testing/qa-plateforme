$ErrorActionPreference='Stop'
$base='https://faicelganem-1791143297915.atlassian.net/wiki'
$root=Split-Path $PSScriptRoot -Parent
$dir=Join-Path $root 'logs/confluence'
if (!$env:CONFLUENCE_EMAIL -or !$env:CONFLUENCE_API_TOKEN) {throw 'Credentials missing'}
$headers=@{Authorization='Basic '+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($env:CONFLUENCE_EMAIL+':'+$env:CONFLUENCE_API_TOKEN));Accept='application/json'}
function Request([string]$route,[string]$method='GET',$body=$null){
 $opts=@{Uri=($base+'/api/v2/'+$route);Method=$method;Headers=$headers;TimeoutSec=30;MaximumRedirection=0}
 if($null -ne $body){$opts.ContentType='application/json; charset=utf-8';$opts.Body=[Text.Encoding]::UTF8.GetBytes(($body|ConvertTo-Json -Depth 20 -Compress))}
 try{$response=Invoke-WebRequest @opts -UseBasicParsing; $reader=[IO.StreamReader]::new($response.RawContentStream,[Text.Encoding]::UTF8); try { $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }}catch{if($_.Exception.Response){throw ('Confluence HTTP '+[int]$_.Exception.Response.StatusCode)};throw 'Confluence network failure'}
}
$parent=Request 'pages/229480?body-format=storage'
if($parent.spaceId -ne '262148'){throw 'Unexpected space'}
$backup=Join-Path $dir 'original-page.json'
if($parent.version.number -eq 1 -or !(Test-Path $backup)){$parent|ConvertTo-Json -Depth 25|Set-Content $backup -Encoding UTF8}
$original=Get-Content $backup -Raw -Encoding UTF8|ConvertFrom-Json
$dossier=Get-Content (Join-Path $dir 'dossier.json') -Raw -Encoding UTF8|ConvertFrom-Json
$pages=@($dossier.pages)+@(@{key='archive';title='QACart Todo | 07 - Sources et publication initiale';html=$original.body.storage.value})
$report=@()
foreach($page in $pages){
 $found=Request ('pages?space-id=262148&title='+[uri]::EscapeDataString($page.title))
 if(@($found.results).Count -gt 1){throw 'Ambiguous child title'}
 if(@($found.results).Count -eq 1){
   $saved=Request ('pages/'+$found.results[0].id+'?body-format=storage')
   $existingText=[Net.WebUtility]::HtmlDecode(($saved.body.storage.value -replace '<[^>]+>','')) -replace '\s',''
   $plannedText=[Net.WebUtility]::HtmlDecode(($page.html -replace '<[^>]+>','')) -replace '\s',''
   if($saved.parentId -ne '229480' -or $existingText -ne $plannedText){throw 'Existing child differs; manual review required'}
 }else{
   $created=Request 'pages' 'POST' @{spaceId='262148';parentId='229480';status='current';title=$page.title;body=@{representation='storage';value=$page.html}}
   $saved=Request ('pages/'+$created.id+'?body-format=storage')
 }
 if($saved.parentId -ne '229480' -or $saved.title -ne $page.title){throw 'Child verification failed'}
 # Verify textual content despite Confluence storage HTML normalization.
 $expected=[Net.WebUtility]::HtmlDecode(($page.html -replace '<[^>]+>','')) -replace '\s',''
 $actual=[Net.WebUtility]::HtmlDecode(($saved.body.storage.value -replace '<[^>]+>','')) -replace '\s',''
 if($expected -ne $actual){throw 'Published text differs from prepared content'}
 $report+=@{key=$page.key;id=$saved.id;title=$saved.title}
 $report|ConvertTo-Json|Set-Content (Join-Path $dir 'dossier-published.json') -Encoding UTF8
 Write-Output ('Verified: '+$page.key)
}
$html='<h2>Référentiel de spécification — QACart Todo</h2><p>Projet UI Playwright BDD. Version documentaire 0.1. Statut : à revoir, non approuvé par le métier.</p><p>Ce dossier sépare les exigences, leurs critères et les preuves de test. Il couvre 9 stories historiques, 29 scénarios distincts et 38 rattachements. La présence de tests ne vaut pas acceptation du produit.</p><h2>Sommaire du dossier</h2><ol>'
foreach($page in $report){$html+='<li><a href="'+$base+'/pages/viewpage.action?pageId='+$page.id+'">'+[Net.WebUtility]::HtmlEncode($page.title)+'</a></li>'}
$html+='</ol><h2>Points nécessitant une décision</h2><p>Consolidation des stories de connexion, clarification de SCRUM-2, confirmation des évolutions de compte, validation de la règle Todo et définition des exigences non fonctionnelles. Responsables et approbateurs : à désigner.</p><h2>Utilisation</h2><p>Consulter les exigences avant les scénarios ; utiliser Allure et Plane pour les résultats datés. La publication initiale et les sources sont conservées dans la section 07. Cette réorganisation ne modifie ni les tests ni les droits de l&#8217;espace et ne configure pas de workflow d&#8217;approbation automatique.</p>'
$updated=Request 'pages/229480' 'PUT' @{id='229480';status='current';title=$parent.title;spaceId='262148';body=@{representation='storage';value=$html};version=@{number=([int]$parent.version.number+1);message='Structuration du dossier de specification et conservation des sources'}}
$check=Request 'pages/229480?body-format=storage'
foreach($page in $report){if(!$check.body.storage.value.Contains('pageId='+$page.id)){throw 'Missing navigation link'}}
Write-Output ('Verified dossier: '+$report.Count+' child pages; parent version '+$check.version.number)
