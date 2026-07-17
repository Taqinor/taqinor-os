"""Sélecteurs LECTURE SEULE de l'app FP&A (apps.fpa)."""
from django.db.models import Sum

from .models import LigneBudgetDepartement


def budget_total_annuel(company, cycle_id, *, departement_id=None, categorie=None):
    """NTFPA3 — total annuel du budget (Σ ``montant_prevu``) pour un cycle,
    éventuellement filtré par département/catégorie. Lecture seule."""
    qs = LigneBudgetDepartement.objects.filter(company=company, cycle_id=cycle_id)
    if departement_id is not None:
        qs = qs.filter(departement_id=departement_id)
    if categorie is not None:
        qs = qs.filter(categorie=categorie)
    return qs.aggregate(total=Sum('montant_prevu'))['total'] or 0


def revenu_engage_carnet(company, mois_debut, mois_fin):
    """NTFPA12 — revenu ENGAGÉ (carnet de commandes) par mois, lu via
    ``ventes.selectors`` (jamais ``ventes.models``). Renvoie ``{'YYYY-MM':
    Decimal}`` — devis acceptés non facturés, 100 % pondéré (déjà signé),
    distinct du pipeline probabiliste NTFPA11 (pas de double-compte)."""
    from apps.ventes import selectors as ventes_selectors

    return ventes_selectors.carnet_commande_par_mois(
        company, mois_debut, mois_fin)
