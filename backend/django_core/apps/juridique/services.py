"""Services (écritures / orchestration) du module ``apps.juridique``.

FRONTIÈRE INTER-APPS — une AUTRE app qui doit écrire ici passe par une
fonction de CE fichier (jamais ``apps.juridique.models`` / ``.views``).

La numérotation des dossiers passe par ``core.numbering`` (race-safe,
plus-haut-utilisé + 1, savepoint + retry) — JAMAIS ``count() + 1``.
"""
from __future__ import annotations


def creer_dossier(company, *, user=None, **champs):
    """Crée un ``DossierJuridique`` avec une référence anti-collision.

    Référence ``JUR-{annee}-{seq}`` (remise à zéro ANNUELLE, padding 4) —
    ``core.numbering.create_with_reference`` gère la course entre deux
    créations simultanées (le perdant prend simplement le numéro suivant).
    La société est TOUJOURS celle passée par l'appelant (posée côté serveur).
    """
    from core.numbering import create_with_reference

    from .models import DossierJuridique

    champs.pop('company', None)
    champs.pop('reference', None)

    def _save(reference):
        return DossierJuridique.objects.create(
            company=company, reference=reference, created_by=user, **champs)

    return create_with_reference(
        DossierJuridique, 'JUR', company, _save, period='yearly')
