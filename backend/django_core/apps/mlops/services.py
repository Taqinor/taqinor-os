"""Services (ÉCRITURE) du module « mlops » (Groupe NTAI, P3)."""
from __future__ import annotations

from django.db import transaction


def activer_version(company, modele_id):
    """NTAI27 — Active UNE version d'un scorer pour une société ; désactive
    toutes les AUTRES versions du MÊME scorer (au plus une active à la fois —
    la contrainte base ``uniq_mlops_modele_actif`` le garantit, ceci en fait
    une opération atomique et sans erreur d'intégrité).

    Renvoie l'instance activée, ou ``None`` si ``modele_id`` n'appartient pas
    à ``company`` (jamais une activation cross-tenant)."""
    from .models import ModeleML

    with transaction.atomic():
        cible = (ModeleML.objects.select_for_update()
                 .filter(company=company, pk=modele_id).first())
        if cible is None:
            return None
        (ModeleML.objects.filter(company=company, nom=cible.nom, actif=True)
         .exclude(pk=cible.pk).update(actif=False))
        if not cible.actif:
            cible.actif = True
            cible.save(update_fields=['actif', 'updated_at'])
    return cible
