"""Lectures publiques du répertoire ``Tiers`` (ARC17).

Point d'entrée READ que les autres apps consommeront (ARC18/19) sans importer
``tiers.models`` : ``tiers`` reste une couche fondation, les domaines
dépendent d'elle, jamais l'inverse.
"""
from .models import Tiers


def tiers_base_qs():
    """Queryset de base (non filtré société) sur les tiers.

    L'appelant DOIT le scoper par société (``.filter(company=…)``) — le
    ``TenantMixin`` du viewset le fait pour l'API.
    """
    return Tiers.objects.all()


def tiers_for_company(company):
    """Tiers d'une société donnée."""
    return Tiers.objects.filter(company=company)


def clients(company):
    """Tiers d'une société marqués comme clients."""
    return tiers_for_company(company).filter(is_client=True)


def fournisseurs(company):
    """Tiers d'une société marqués comme fournisseurs."""
    return tiers_for_company(company).filter(is_fournisseur=True)


def get_tiers(company, tiers_id):
    """Récupère un tiers scopé société, ou ``None``."""
    return tiers_for_company(company).filter(pk=tiers_id).first()
