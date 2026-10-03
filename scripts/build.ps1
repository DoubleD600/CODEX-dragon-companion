param([string]$Python = "python")
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & $Python -m pip install . -r requirements-build.txt
    if($LASTEXITCODE -ne 0){throw 'Dependency installation failed'}
    & $Python -m PyInstaller --noconfirm dragon-companion.spec
    if($LASTEXITCODE -ne 0){throw 'Build failed'}
    Copy-Item README.md, LICENSE, ASSETS.md, config.example.json, ARCHITECTURE.md, CHANGELOG.md -Destination dist/DragonCompanion
    Copy-Item examples -Destination dist/DragonCompanion -Recurse -Force
    $licenses = Join-Path $root 'dist/DragonCompanion/THIRD_PARTY_LICENSES'
    New-Item -ItemType Directory -Force -Path $licenses | Out-Null
    Copy-Item -Path (Join-Path $root 'third_party/*') -Destination $licenses -Recurse
    Compress-Archive -Path dist/DragonCompanion -DestinationPath dist/DragonCompanion-v1.0.0-windows-x64.zip -Force
    & git archive --format=zip --prefix=dragon-companion-1.0.0/ --output=dist/dragon-companion-v1.0.0-source.zip HEAD
    if($LASTEXITCODE -ne 0){throw 'Source archive failed'}
    Get-ChildItem dist -Filter '*.zip' | ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "$($hash.Hash.ToLower())  $($_.Name)"
    } | Set-Content -Encoding ascii dist/SHA256SUMS.txt
} finally {Pop-Location}
