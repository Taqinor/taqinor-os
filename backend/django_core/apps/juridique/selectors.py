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


# ── NTJUR19 — résolution de la règle d'approbation d'un engagement ──────────


def regles_approbation_actives(company):
    """Règles d'approbation juridique ACTIVES de la société."""
    from .models import RegleApprobationJuridique

    return RegleApprobationJuridique.objects.filter(
        company=company, actif=True)


def resoudre_regle_approbation_mandat(company, montant, nature_dossier=None):
    """Règle la plus SPÉCIFIQUE couvrant (montant, nature), ou ``None``.

    Spécificité, dans l'ordre (patron ``contrats.selectors``) :
    1. une règle ciblant une nature précise prime sur « toutes natures » ;
    2. à ce niveau égal, l'intervalle de montant BORNÉ le plus étroit prime ;
    3. puis ``priorite`` (plus grande d'abord), puis l'``id`` le plus récent.

    Aucun seuil codé en dur : tout vient des règles en base. ``None`` signifie
    « aucune approbation requise » — l'appelant peut activer directement.
    """
    candidates = [
        r for r in regles_approbation_actives(company)
        if r.couvre(montant, nature_dossier)
    ]
    if not candidates:
        return None

    def _cle(regle):
        nature_specifique = 1 if regle.nature_dossier else 0
        largeur = regle.largeur_intervalle()
        intervalle_borne = 1 if largeur is not None else 0
        largeur_tri = -largeur if largeur is not None else 0
        return (nature_specifique, intervalle_borne, largeur_tri,
                regle.priorite, regle.id)

    candidates.sort(key=_cle, reverse=True)
    return candidates[0]
