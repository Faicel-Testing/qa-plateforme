$ErrorActionPreference = 'Stop'
$destination = Join-Path $PSScriptRoot '../logs/plane/windows-ca.pem'
$certificates = Get-ChildItem Cert:\CurrentUser\Root,Cert:\LocalMachine\Root,Cert:\CurrentUser\CA,Cert:\LocalMachine\CA
$pem = foreach ($certificate in ($certificates | Sort-Object Thumbprint -Unique)) {
  '-----BEGIN CERTIFICATE-----'
  [Convert]::ToBase64String($certificate.RawData, [Base64FormattingOptions]::InsertLineBreaks)
  '-----END CERTIFICATE-----'
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
[IO.File]::WriteAllText($destination, ($pem -join "`n"), [Text.Encoding]::ASCII)
Write-Output 'Public Windows certificate bundle exported for Plane TLS verification'
