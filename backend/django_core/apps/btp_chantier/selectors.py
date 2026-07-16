"""Sélecteurs LECTURE SEULE du vertical BTP/EPC (Groupe NTCON).

Les lectures cross-app (chantier ↔ projets, situations, sous-traitance,
retenue de garantie…) passent par ``django.apps.apps.get_model`` — jamais un
import statique de modèle d'une autre app (pattern déjà utilisé par
``installations/selectors.py`` et ``paie/services.py`` pour les lectures
cross-app sans arête d'import ; JAMAIS pour une écriture).
"""
from __future__ import annotations

from django.utils import timezone

from .models import RFI, ReserveChantier


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


# ── NTCON3 — RFI ─────────────────────────────────────────────────────────────

def rfi_filtres(qs, *, chantier_id=None, statut=None):
    """Filtres optionnels ``?chantier=&statut=`` (queryset déjà scopé société).

    L'ordre par défaut (``RFI.Meta.ordering``) trie déjà par
    ``date_limite_reponse`` ascendant — un RFI en retard (échéance passée)
    apparaît donc TOUJOURS avant un RFI encore dans les temps.
    """
    if chantier_id not in (None, ''):
        qs = qs.filter(chantier_id=chantier_id)
    if statut not in (None, ''):
        qs = qs.filter(statut=statut)
    return qs


def rfi_en_retard(company=None, *, chantier=None):
    """``RFI`` ouverts dont l'échéance de réponse est dépassée (lecture).

    ``company=None`` (défaut) balaie TOUTES les sociétés — usage sweep
    Celery beat (``alertes_rfi_retard``, NTCON4) ; un appelant scopé société
    (vue/API) passe explicitement sa société.
    """
    qs = RFI.objects.filter(
        statut=RFI.Statut.OUVERT,
        date_limite_reponse__lt=timezone.localdate())
    if company is not None:
        qs = qs.filter(company=company)
    if chantier is not None:
        qs = qs.filter(chantier=chantier)
    return qs
