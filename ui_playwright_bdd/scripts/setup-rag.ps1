$ErrorActionPreference = 'Stop'
$frameworkRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $frameworkRoot
try {
    $env:RAG_MODE = 'bm25'
    & node (Join-Path $PSScriptRoot 'rag.js') index
    if ($LASTEXITCODE -ne 0) { throw 'BM25 indexing failed.' }
} finally { Pop-Location }
