param([string]$Owner = 'DoubleD600', [string]$Repository = 'dragon-companion', [string]$Gh = 'gh')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & $Gh auth status --hostname github.com
    if($LASTEXITCODE -ne 0){throw 'Authorize GitHub CLI before publishing'}
    $repo = "$Owner/$Repository"
    & $Gh repo view $repo --json nameWithOwner
    if($LASTEXITCODE -ne 0){
        & $Gh repo create $repo --public --source $root --remote origin --push --description 'A lightweight Qt dragon desktop companion with local Codex task and usage panels'
        if($LASTEXITCODE -ne 0){throw 'Repository creation failed'}
    } else {
        $remote = & git remote get-url origin
        if($LASTEXITCODE -ne 0){& git remote add origin "https://github.com/$repo.git"}
        elseif($remote -notmatch [regex]::Escape($repo)){throw 'Origin points to a different repository'}
        & git push origin main
        if($LASTEXITCODE -ne 0){throw 'Source push failed'}
    }
    & git push origin v1.0.0
    if($LASTEXITCODE -ne 0){throw 'Tag push failed'}
    & $Gh release view v1.0.0 --repo $repo
    if($LASTEXITCODE -ne 0){
        & $Gh release create v1.0.0 --repo $repo --title 'Dragon Companion v1.0.0' --notes-file RELEASE_NOTES.md dist/DragonCompanion-v1.0.0-windows-x64.zip dist/dragon-companion-v1.0.0-source.zip dist/SHA256SUMS.txt
    } else {
        & $Gh release upload v1.0.0 --repo $repo dist/DragonCompanion-v1.0.0-windows-x64.zip dist/dragon-companion-v1.0.0-source.zip dist/SHA256SUMS.txt --clobber
    }
    if($LASTEXITCODE -ne 0){throw 'Release upload failed'}
} finally {Pop-Location}
