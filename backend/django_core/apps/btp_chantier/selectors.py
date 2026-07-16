"""Sélecteurs LECTURE SEULE du vertical BTP/EPC (Groupe NTCON).

Les lectures cross-app (chantier ↔ projets, situations, sous-traitance,
retenue de garantie…) passent par ``django.apps.apps.get_model`` — jamais un
import statique de modèle d'une autre app (pattern déjà utilisé par
``installations/selectors.py`` et ``paie/services.py`` pour les lectures
cross-app sans arête d'import ; JAMAIS pour une écriture).
"""
from __future__ import annotations

from .models import ReserveChantier


# ── NTCON1 — Réserves de chantier ───────────────────────────────────────────

def reserves_filtrees(qs, *, lot=None, statut=None, gravite=None, chantier_id=None):
    """Applique les filtres optionnels ``?lot=&statut=&gravite=&chantier=``.

    ``qs`` est déjà scopé société par l'appelant (``TenantMixin``). Lecture
    seule, ne modifie jamais le queryset d'origine.
    """
    if lot not in (None, ''):
        qs = qs.filter(lot__icontains=lot)
    if statut not in (None, ''):
        qs = qs.filter(statut=statut)
    if gravite not in (None, ''):
        qs = qs.filter(gravite=gravite)
    if chantier_id not in (None, ''):
        qs = qs.filter(chantier_id=chantier_id)
    return qs


def reserves_actives_bloquantes(company, chantier=None):
    """``ReserveChantier`` ouvertes/en cours de gravité bloquante (lecture)."""
    qs = ReserveChantier.objects.filter(
        company=company,
        gravite=ReserveChantier.Gravite.BLOQUANTE,
        statut__in=[ReserveChantier.Statut.OUVERTE, ReserveChantier.Statut.EN_COURS],
    )
    if chantier is not None:
        qs = qs.filter(chantier=chantier)
    return qs
