"""Sélecteurs (lectures) du module ``apps.juridique`` (groupe NTJUR).

FRONTIÈRE INTER-APPS — une AUTRE app qui a besoin de LIRE des données
juridiques passe par une fonction de CE fichier (jamais un import de
``apps.juridique.models`` / ``.views``). Imports paresseux (fonction-locaux)
pour ne jamais créer de cycle au chargement des apps.
"""
from __future__ import annotations


def peut_voir_confidentiel(user):
    """Vrai si ``user`` a le droit de voir les dossiers CONFIDENTIELS.

    Palier faisant autorité : ``CustomUser.menu_tier`` (dérivé du Role FK,
    renvoie le palier admin pour un superuser) — jamais ``role_legacy``, peu
    fiable pour un administrateur provisionné via le Role FK. Même patron que
    ``contrats.ContratViewSet.get_queryset`` (CONTRAT6).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    role_admin = getattr(user, 'ROLE_ADMIN', None)
    if role_admin is None:
        return False
    return getattr(user, 'menu_tier', None) == role_admin


def dossiers_visibles(company, user=None):
    """Dossiers juridiques de ``company``, filtrés par confidentialité.

    Un dossier ``confidentiel`` est EXCLU (invisible, pas 403) pour un
    utilisateur sans le palier requis — y compris son propre responsable
    interne : c'est ce qui protège les dossiers RH/direction.
    """
    from .models import DossierJuridique

    qs = DossierJuridique.objects.filter(company=company)
    if user is not None and not peut_voir_confidentiel(user):
        qs = qs.exclude(
            confidentialite=DossierJuridique.NiveauConfidentialite.CONFIDENTIEL)
    return qs


def dossier_par_id(company, dossier_id, user=None):
    """Un dossier de ``company`` par id (ou ``None``), filtrage confidentialité
    appliqué — lecture cross-app sûre."""
    return dossiers_visibles(company, user=user).filter(pk=dossier_id).first()
