$ErrorActionPreference = 'Stop'
$frameworkRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$instanceRoot = Join-Path $frameworkRoot '.qa-test-db'
$clusterPath = Join-Path $instanceRoot 'data'
$binPath = 'C:\Program Files\PostgreSQL\18\bin'
$port = 5433
if (-not (Test-Path -LiteralPath (Join-Path $binPath 'initdb.exe'))) { throw 'PostgreSQL 18 binaries not found' }
New-Item -ItemType Directory -Path $instanceRoot -Force | Out-Null
$secretPath = Join-Path $instanceRoot 'admin-password.txt'
$appSecretPath = Join-Path $instanceRoot 'application-password.txt'
function New-LocalPassword {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes)
}
if (-not (Test-Path -LiteralPath (Join-Path $clusterPath 'PG_VERSION'))) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw 'Port 5433 is already in use; no existing instance changed' }
    [IO.File]::WriteAllText($secretPath, (New-LocalPassword), [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($appSecretPath, (New-LocalPassword), [Text.UTF8Encoding]::new($false))
    & (Join-Path $binPath 'initdb.exe') -D $clusterPath -U qa_test_admin --encoding=UTF8 --locale=C --auth-host=scram-sha-256 --auth-local=scram-sha-256 --pwfile=$secretPath
    if ($LASTEXITCODE -ne 0) { throw 'Dedicated cluster initialization failed' }
}
& (Join-Path $binPath 'pg_ctl.exe') -D $clusterPath status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    $arguments = '-D "' + $clusterPath + '" -l "' + (Join-Path $instanceRoot 'server.log') + '" -o "-p 5433 -h 127.0.0.1" -w start'
    $start = Start-Process -FilePath (Join-Path $binPath 'pg_ctl.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
    if (-not $start.WaitForExit(30000)) { throw 'PostgreSQL startup timed out; inspect the instance log' }
    if ($start.ExitCode -ne 0) { throw 'Dedicated PostgreSQL startup failed; see .qa-test-db/server.log' }
}
$savedPassword = $env:PGPASSWORD
$savedAppPassword = $env:QA_DATA_APPLICATION_PASSWORD
try {
    $env:PGPASSWORD = [IO.File]::ReadAllText($secretPath).Trim()
    $env:QA_DATA_APPLICATION_PASSWORD = [IO.File]::ReadAllText($appSecretPath).Trim()
    $sql = @'
\getenv app_password QA_DATA_APPLICATION_PASSWORD
SELECT format('CREATE ROLE qa_data LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='qa_data') \gexec
SELECT 'CREATE DATABASE qa_test_data OWNER qa_data'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='qa_test_data') \gexec
'@
    $sql | & (Join-Path $binPath 'psql.exe') -X -q -w -h 127.0.0.1 -p $port -U qa_test_admin -d postgres -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw 'Dedicated database provisioning failed' }
    $envFile = Join-Path $frameworkRoot '.env'
    $content = if (Test-Path -LiteralPath $envFile) { [IO.File]::ReadAllText($envFile) } else { '' }
    $settings = @{TEST_DATA_PROVIDER='postgres';TEST_DATA_PGHOST='127.0.0.1';TEST_DATA_PGPORT='5433';TEST_DATA_PGDATABASE='qa_test_data';TEST_DATA_PGUSER='qa_data';TEST_DATA_PGPASSWORD=$env:QA_DATA_APPLICATION_PASSWORD}
    foreach ($name in $settings.Keys) {
        $line = $name + '=' + $settings[$name]
        $pattern = '(?m)^' + $name + '=.*$'
        if ([regex]::IsMatch($content,$pattern)) { $content=[regex]::Replace($content,$pattern,[Text.RegularExpressions.MatchEvaluator]{param($match) $line}) }
        else { $content += "`r`n" + $line }
    }
    [IO.File]::WriteAllText($envFile,$content+"`r`n",[Text.UTF8Encoding]::new($false))
    Write-Output 'Dedicated PostgreSQL ready: 127.0.0.1:5433 / qa_test_data / qa_data. Credentials configured locally.'
} finally { $env:PGPASSWORD=$savedPassword; $env:QA_DATA_APPLICATION_PASSWORD=$savedAppPassword }
