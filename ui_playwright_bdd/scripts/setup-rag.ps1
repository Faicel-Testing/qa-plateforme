$ErrorActionPreference = 'Stop'
$frameworkRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $frameworkRoot
try {
    & node (Join-Path $PSScriptRoot 'setup-embeddings.cjs')
    if ($LASTEXITCODE -ne 0) { throw 'Local embedding model installation failed.' }
    $env:RAG_MODE = 'hybrid'
    & node (Join-Path $PSScriptRoot 'rag.js') index
    if ($LASTEXITCODE -ne 0) { throw 'Hybrid indexing failed.' }
} finally { Pop-Location }
