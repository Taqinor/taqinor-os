# Sauvegarde de secours (disaster-recovery) — GitHub reste la source de
# vérité du dépôt ; ce bundle est une sécurité en plus, pas un remplacement.
#
# Disaster-recovery backup — GitHub stays the source of truth for the repo;
# this bundle is a belt-and-suspenders safety net, not a replacement.
#
# ⚠ AVERTISSEMENT CRITIQUE / CRITICAL WARNING ⚠
# Ne JAMAIS synchroniser le dépôt de travail (ni aucun worktree) avec
# OneDrive/Dropbox/iCloud etc. — la synchronisation cloud d'un .git EN VIE le
# corrompt (fichiers verrouillés en cours d'écriture, renommages atomiques
# cassés par la sync, index Git désynchronisé). Ce script produit un SEUL
# fichier bundle statique (immuable une fois créé) dans un dossier synchronisé
# — c'est la façon sûre d'obtenir une copie de secours dans le cloud.
#
# NEVER OneDrive/Dropbox/iCloud-sync the live working repo or any worktree —
# cloud-syncing a LIVE .git corrupts it (files locked mid-write, atomic
# renames broken by the sync, desynced Git index). This script instead
# produces a SINGLE static bundle file (immutable once created) inside a
# synced folder — that is the safe way to get a cloud-backed copy.
#
# Usage :
#   powershell -File scripts\backup-bundle.ps1
#   powershell -File scripts\backup-bundle.ps1 -Dest "D:\backups\taqinor"

param(
    [string]$Dest = "$env:USERPROFILE\OneDrive\taqinor-backups"
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    # ── Créer le dossier de destination si absent ───────────────────────────
    if (-not (Test-Path -LiteralPath $Dest)) {
        Write-Host "→ Création du dossier de destination : $Dest"
        New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    }

    $Timestamp = Get-Date -Format 'yyyyMMdd-HHmm'
    $BundleName = "taqinor-$Timestamp.bundle"
    $BundlePath = Join-Path $Dest $BundleName

    # ── Créer le bundle (dépôt complet, toutes les branches) ───────────────
    # Create the bundle (full repo, all branches).
    Write-Host "→ Création du bundle : $BundlePath"
    git bundle create $BundlePath --all
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Échec de 'git bundle create' — voir la sortie ci-dessus."
        exit 1
    }

    # ── Vérifier le bundle après création ───────────────────────────────────
    # Verify the bundle after creation.
    Write-Host "→ Vérification du bundle…"
    git bundle verify $BundlePath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Le bundle créé n'a pas passé 'git bundle verify' — sauvegarde suspecte, à ne pas garder telle quelle."
        exit 1
    }
    Write-Host "  OK — bundle vérifié."

    # ── Rotation 7 jours ─────────────────────────────────────────────────────
    # 7-day rotation: delete bundles older than 7 days in that folder.
    Write-Host "→ Rotation : suppression des bundles de plus de 7 jours dans $Dest…"
    $cutoff = (Get-Date).AddDays(-7)
    $oldBundles = Get-ChildItem -LiteralPath $Dest -Filter 'taqinor-*.bundle' -File |
        Where-Object { $_.LastWriteTime -lt $cutoff }

    if ($oldBundles) {
        foreach ($old in $oldBundles) {
            Write-Host "  Suppression : $($old.Name) (modifié le $($old.LastWriteTime))"
            Remove-Item -LiteralPath $old.FullName -Force
        }
    } else {
        Write-Host "  Aucun bundle à faire tourner (rien de plus vieux que 7 jours)."
    }

    $sizeMb = [Math]::Round((Get-Item -LiteralPath $BundlePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "✓ Sauvegarde terminée : $BundlePath ($sizeMb Mo)" -ForegroundColor Green
}
finally {
    Pop-Location
}
