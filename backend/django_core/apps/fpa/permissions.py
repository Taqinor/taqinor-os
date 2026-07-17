"""NTFPA26 — périmètre d'accès FP&A par département.

Codes de permission FP&A (réutilisent ``Role.permissions`` JSON, aucun nouveau
modèle) :

* ``fpa_saisir``          — saisir le budget de SON département ;
* ``fpa_valider``         — valider/rejeter un budget soumis ;
* ``fpa_consulter_tout``  — voir tous les départements ;
* ``fpa_administrer``     — administration complète FP&A.

NB — l'enregistrement de ces codes dans ``apps/roles/models.ALL_PERMISSIONS``
(pour les rendre assignables depuis l'UI de gestion des rôles) est HORS
PÉRIMÈTRE de la session FINANCE (``apps/roles`` appartient à la plateforme) :
il reste à faire par le run plateforme. L'ENFORCEMENT côté FP&A ci-dessous est
complet et indépendant : un utilisateur limité à son département reçoit bien un
403 sur le budget d'un autre département.
"""

FPA_SAISIR = 'fpa_saisir'
FPA_VALIDER = 'fpa_valider'
FPA_CONSULTER_TOUT = 'fpa_consulter_tout'
FPA_ADMINISTRER = 'fpa_administrer'


def peut_tout_voir(user):
    """Vrai si l'utilisateur voit TOUS les départements : superuser, palier
    Directeur/Administrateur (repli légacy), ou porteur de ``fpa_consulter_tout``
    / ``fpa_administrer``."""
    if not (user and getattr(user, 'is_authenticated', False)):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    for code in (FPA_CONSULTER_TOUT, FPA_ADMINISTRER):
        try:
            if user.has_erp_permission(code):
                return True
        except Exception:
            pass
    # Repli de palier : Directeur/Administrateur voient tout (comportement
    # historique préservé pour les comptes hérités sans rôle fin FP&A).
    return bool(getattr(user, 'is_admin_role', False)
                or getattr(user, 'is_responsable', False))


def departements_visibles_ids(user, company):
    """Ensemble des ids de départements que ``user`` peut voir/éditer.

    ``None`` = tous (l'appelant ne filtre pas). Sinon : les départements dont
    l'utilisateur est responsable + tout leur sous-arbre."""
    if peut_tout_voir(user):
        return None
    from .models import Departement

    ids = set()
    for dept in Departement.objects.filter(company=company, responsable=user):
        ids |= dept.sous_arbre_ids()
    return ids
