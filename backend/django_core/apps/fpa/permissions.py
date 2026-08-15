"""NTFPA26 — périmètre d'accès FP&A par département.

Codes de permission FP&A (réutilisent ``Role.permissions`` JSON, aucun nouveau
modèle) :

* ``fpa_saisir``          — saisir le budget de SON département ;
* ``fpa_valider``         — valider/rejeter un budget soumis ;
* ``fpa_consulter_tout``  — voir tous les départements ;
* ``fpa_administrer``     — administration complète FP&A.

WIR173 — les quatre codes sont désormais ENREGISTRÉS au catalogue
(``apps/roles/models.ALL_PERMISSIONS``, run plateforme) ET posés en GARDE sur
les 14 viewsets FP&A : jusque-là, aucun viewset FP&A ne portait la moindre
``permission_classes``, donc tout utilisateur AUTHENTIFIÉ pouvait lire ET
écrire cycles, scénarios, masse salariale et l'export XLSX. Le périmètre par
département (``departements_visibles_ids``) reste EN PLUS de cette garde : il
restreint, il n'autorise pas.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

# ``_user_has_or_legacy`` est la brique de repli légacy du dépôt (core est une
# app de FONDATION) : un compte SANS rôle fin garde son comportement historique
# (palier Responsable/Admin). On la réutilise plutôt que de la réécrire, pour
# que FP&A ait EXACTEMENT la même sémantique que ``core.ScopedPermission``.
from core.permissions import _user_has_or_legacy

FPA_SAISIR = 'fpa_saisir'
FPA_VALIDER = 'fpa_valider'
FPA_CONSULTER_TOUT = 'fpa_consulter_tout'
FPA_ADMINISTRER = 'fpa_administrer'

#: WIR173 — lire FP&A : n'importe lequel des quatre codes suffit (le périmètre
#: par département restreint ensuite ce que le porteur voit réellement).
LECTURE_FPA = (
    FPA_SAISIR, FPA_VALIDER, FPA_CONSULTER_TOUT, FPA_ADMINISTRER)
#: WIR173 — écrire FP&A : ``fpa_consulter_tout`` est un droit de LECTURE seule,
#: il n'ouvre aucune écriture.
ECRITURE_FPA = (FPA_SAISIR, FPA_VALIDER, FPA_ADMINISTRER)


class ScopedPermissionFpa(BasePermission):
    """WIR173 — ``core.ScopedPermission`` avec des codes MULTIPLES.

    Même routage lecture/écriture par méthode HTTP et même repli légacy que
    ``core.ScopedPermission``, mais ``read_permission``/``write_permission``
    peuvent être un TUPLE de codes : le porteur passe s'il en détient AU MOINS
    UN. FP&A en a besoin parce que quatre rôles distincts (saisie, validation,
    consultation globale, administration) lisent la même surface.

    ``None`` (ou tuple vide) d'un côté = « authentifié suffit » de ce côté —
    strictement la sémantique de ``core.ScopedPermission``.
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route interne.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        if request.method in SAFE_METHODS:
            codes = getattr(view, 'read_permission', None)
        else:
            codes = getattr(view, 'write_permission', None)
        if not codes:
            return True
        if isinstance(codes, str):
            codes = (codes,)
        if any(_user_has_or_legacy(user, code) for code in codes):
            return True
        # NTFPA26 — la SECONDE porte d'entrée légitime de FP&A, préservée
        # telle quelle : être RESPONSABLE d'un département, c'est se voir
        # confier la saisie de son budget. Cet accès reste étroitement borné
        # par ``departements_visibles_ids`` (le porteur ne voit et n'écrit que
        # son sous-arbre — testé par ``test_ntfpa26_permission_perimetre``).
        # Sans cette porte, WIR173 casserait le périmètre par département au
        # lieu de le garder.
        return est_responsable_departement(user)


def est_responsable_departement(user):
    """Vrai si ``user`` est responsable d'au moins un département FP&A de sa
    société (porte d'accès NTFPA26)."""
    company_id = getattr(user, 'company_id', None)
    if not company_id:
        return False
    from .models import Departement
    return Departement.objects.filter(
        company_id=company_id, responsable=user).exists()


class FpaScopedMixin:
    """Défaut FP&A : lecture = un des 4 codes, écriture = un des 3 codes
    d'action. Un viewset qui a besoin d'autre chose surcharge simplement
    ``read_permission``/``write_permission``.
    """

    permission_classes = [ScopedPermissionFpa]
    read_permission = LECTURE_FPA
    write_permission = ECRITURE_FPA


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
