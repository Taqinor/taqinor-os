"""FG395 — Sauvegarde / restauration en libre-service (par société).

Couche de FONDATION : matérialise un BUNDLE des données d'une société (export)
et trace une RESTAURATION, SANS que ``core`` n'importe une app métier (contrat
import-linter ``core-foundation-is-a-base-layer``). Les données proviennent
EXCLUSIVEMENT du registre de datasets de l'explorateur (``core.data_explorer``),
dont chaque ``queryset_provider`` est DÉJÀ scopé par société : ``core`` agrège
sans rien connaître du métier.

Conception
----------

* ``construire_manifeste(company, user, datasets=None)`` — pour chaque dataset
  enregistré (ou la sous-liste demandée), compte les lignes scopées société et
  renvoie un manifeste ``{datasets: [{name, label, lignes}], total_lignes}``.
* ``executer_sauvegarde(run)`` — remplit le manifeste du ``BackupRun`` (export),
  passe ``statut`` à ``termine`` et horodate ``termine_le``. La matérialisation
  d'un artefact physique (fichier/objet de stockage) reste un no-op tant
  qu'aucune destination n'est branchée — l'opération réussit (manifeste produit)
  sans dépendance externe.
* ``executer_restauration(run)`` — une restauration RÉELLE écrasant des données
  vivantes exige une validation et un magasin d'artefacts provisionnés par le
  fondateur (AUTH/destructif). Tant que ces prérequis ne sont pas branchés, la
  restauration est tracée en ``non_configure`` (jamais d'écriture aveugle) — le
  contrat de fondation est préservé et l'opération est revertable.

Aucune importation d'app domaine ici : seulement ``core.data_explorer`` (registre
en mémoire) et l'ORM générique.
"""
from __future__ import annotations

from django.utils import timezone

from . import data_explorer
from .models import BackupRun


def _datasets_cibles(datasets):
    """Liste de noms de datasets à inclure (vide → tous les enregistrés)."""
    connus = {d['name']: d for d in data_explorer.list_datasets()}
    if not datasets:
        return list(connus.values())
    out = []
    for name in datasets:
        d = connus.get(name)
        if d is not None:
            out.append(d)
    return out


def construire_manifeste(company, user=None, datasets=None):
    """Construit le manifeste d'un bundle de sauvegarde pour ``company``.

    Compte les lignes scopées société par dataset (le ``queryset_provider`` du
    dataset garantit le scoping). Renvoie un dict JSON-sérialisable.
    """
    lignes_par_dataset = []
    total = 0
    for d in _datasets_cibles(datasets):
        name = d['name']
        try:
            ds = data_explorer.get_dataset(name)
            qs = ds['provider'](company, user)
            nb = qs.count()
        except Exception as exc:  # noqa: BLE001 — dataset défaillant n'arrête pas
            lignes_par_dataset.append(
                {'name': name, 'label': d['label'], 'erreur': str(exc)})
            continue
        total += nb
        lignes_par_dataset.append(
            {'name': name, 'label': d['label'], 'lignes': nb})
    return {
        'datasets': lignes_par_dataset,
        'total_lignes': total,
        'genere_le': timezone.now().isoformat(),
    }


def executer_sauvegarde(run: BackupRun):
    """Exécute une sauvegarde (export) : remplit le manifeste, marque terminé.

    Ne dépend d'aucun service externe : produit toujours un manifeste. La
    matérialisation d'un artefact physique reste optionnelle (no-op si aucune
    destination de stockage n'est configurée).
    """
    run.statut = BackupRun.STATUT_EN_COURS
    run.save(update_fields=['statut', 'updated_at'])
    manifeste = construire_manifeste(run.company, run.declenche_par,
                                     run.datasets)
    run.manifest = manifeste
    run.statut = BackupRun.STATUT_TERMINE
    run.termine_le = timezone.now()
    run.detail = {'message': 'Manifeste de sauvegarde produit.'}
    run.save(update_fields=['manifest', 'statut', 'termine_le', 'detail',
                            'updated_at'])
    return run


def executer_restauration(run: BackupRun):
    """Trace une restauration.

    Une restauration RÉELLE (écriture/écrasement de données vivantes) exige un
    magasin d'artefacts et une validation provisionnés par le fondateur
    (AUTH/destructif). Tant qu'ils ne sont pas branchés, l'opération est tracée
    en ``non_configure`` SANS écrire — jamais d'écriture aveugle.
    """
    if not run.artifact_ref:
        run.statut = BackupRun.STATUT_NON_CONFIGURE
        run.detail = {
            'message': "Aucun artefact source : restauration non configurée "
                       "(magasin d'artefacts à provisionner par le fondateur).",
        }
        run.save(update_fields=['statut', 'detail', 'updated_at'])
        return run
    # Avec un artefact branché mais sans pipeline de restauration validé, on
    # reste en no-op tracé : la fondation ne réalise aucune écriture métier.
    run.statut = BackupRun.STATUT_NON_CONFIGURE
    run.detail = {
        'message': 'Pipeline de restauration non branché (no-op tracé).',
        'artifact_ref': run.artifact_ref,
    }
    run.save(update_fields=['statut', 'detail', 'updated_at'])
    return run
