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
