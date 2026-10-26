$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$bin='C:\Program Files\PostgreSQL\18\bin'
$instance=Join-Path $root '.qa-test-db'
$admin=Join-Path $instance 'admin-password.txt'
$secret=Join-Path $instance 'rag-password.txt'
$source=Join-Path $root '.qa-rag/pgvector-src'
$extensionRoot=Join-Path $root '.qa-rag/pgvector-extension'
$extensionShare=Join-Path $extensionRoot 'share'
$extensionFiles=Join-Path $extensionShare 'extension'
$extensionLib=Join-Path $extensionRoot 'lib'
if (-not (Test-Path -LiteralPath (Join-Path $source 'vector.dll'))) { throw 'Compile pgvector first: cmd /c scripts\build-pgvector.cmd' }
New-Item -ItemType Directory -Force -Path $extensionFiles,$extensionLib | Out-Null
$dll=Join-Path $extensionLib 'vector.dll'
if (-not (Test-Path -LiteralPath $dll)) { Copy-Item -LiteralPath (Join-Path $source 'vector.dll') -Destination $dll }
elseif ((Get-FileHash -LiteralPath $dll).Hash -ne (Get-FileHash -LiteralPath (Join-Path $source 'vector.dll')).Hash) { throw 'Extension DLL differs: plan an explicit PostgreSQL maintenance window before upgrading.' }
$modulePath=(Join-Path $extensionLib 'vector').Replace('\','/')
$control=[IO.File]::ReadAllText((Join-Path $source 'vector.control')).Replace('''$libdir/vector''',("'"+$modulePath.Replace("'","''")+"'"))
[IO.File]::WriteAllText((Join-Path $extensionFiles 'vector.control'),$control,[Text.UTF8Encoding]::new($false))
Copy-Item -Path (Join-Path $source 'sql/vector--*.sql') -Destination $extensionFiles -Force
if (-not (Test-Path -LiteralPath $admin)) { throw 'Dedicated PostgreSQL instance missing; run npm run data:setup first.' }
if (-not (Test-Path -LiteralPath $secret)) {
  $bytes=New-Object byte[] 32
  $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  [IO.File]::WriteAllText($secret,[Convert]::ToBase64String($bytes),[Text.UTF8Encoding]::new($false))
}
$savedPassword=$env:PGPASSWORD
$savedRag=$env:QA_RAG_APPLICATION_PASSWORD
$savedExtension=$env:QA_RAG_EXTENSION_PATH
try {
  $env:PGPASSWORD=[IO.File]::ReadAllText($admin).Trim()
  $env:QA_RAG_APPLICATION_PASSWORD=[IO.File]::ReadAllText($secret).Trim()
  $env:QA_RAG_EXTENSION_PATH=$extensionShare.Replace('\','/')+';$system'
  $sql=@'
\getenv rag_password QA_RAG_APPLICATION_PASSWORD
SELECT format('CREATE ROLE qa_rag LOGIN PASSWORD %L', :'rag_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='qa_rag') \gexec
SELECT 'CREATE DATABASE qa_rag OWNER qa_rag'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='qa_rag') \gexec
REVOKE CONNECT ON DATABASE qa_rag FROM PUBLIC;
GRANT CONNECT ON DATABASE qa_rag TO qa_rag;
'@
  $sql | & (Join-Path $bin 'psql.exe') -X -q -w -h 127.0.0.1 -p 5433 -U qa_test_admin -d postgres -v ON_ERROR_STOP=1
  if ($LASTEXITCODE -ne 0) { throw 'RAG database provisioning failed.' }
  $extensionSql=@'
\getenv extension_path QA_RAG_EXTENSION_PATH
ALTER DATABASE qa_rag SET extension_control_path TO :'extension_path';
SET extension_control_path TO :'extension_path';
CREATE EXTENSION IF NOT EXISTS vector;
'@
  $extensionSql | & (Join-Path $bin 'psql.exe') -X -q -w -h 127.0.0.1 -p 5433 -U qa_test_admin -d qa_rag -v ON_ERROR_STOP=1
  if ($LASTEXITCODE -ne 0) { throw 'pgvector extension unavailable; install pgvector for PostgreSQL 18 first.' }
  $env:PGPASSWORD=$env:QA_RAG_APPLICATION_PASSWORD
  & (Join-Path $bin 'psql.exe') -X -q -w -h 127.0.0.1 -p 5433 -U qa_rag -d qa_rag -v ON_ERROR_STOP=1 -f (Join-Path $root 'database/migrations/002_rag_pgvector.sql')
  if ($LASTEXITCODE -ne 0) { throw 'RAG schema migration failed.' }
  $envFile=Join-Path $root '.env'
  $content=[IO.File]::ReadAllText($envFile)
  $settings=@{RAG_VECTOR_STORE='pgvector';RAG_MODE='hybrid';RAG_PGHOST='127.0.0.1';RAG_PGPORT='5433';RAG_PGDATABASE='qa_rag';RAG_PGUSER='qa_rag';RAG_PGPASSWORD=$env:QA_RAG_APPLICATION_PASSWORD}
  foreach ($name in $settings.Keys) {
    $line=$name+'='+$settings[$name]
    $pattern='(?m)^'+$name+'=.*$'
    if ([regex]::IsMatch($content,$pattern)) { $content=[regex]::Replace($content,$pattern,[Text.RegularExpressions.MatchEvaluator]{param($match) $line}) }
    else { $content+="`r`n"+$line }
  }
  [IO.File]::WriteAllText($envFile,$content+"`r`n",[Text.UTF8Encoding]::new($false))
  Write-Output 'pgvector ready: 127.0.0.1:5433 / qa_rag. Dedicated non-superuser credentials configured locally.'
} finally { $env:PGPASSWORD=$savedPassword; $env:QA_RAG_APPLICATION_PASSWORD=$savedRag; $env:QA_RAG_EXTENSION_PATH=$savedExtension }
