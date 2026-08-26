"""NTFPA26 + WIR173 — contrôle d'accès FP&A (périmètre + gardes de viewset).

Codes de permission FP&A (réutilisent ``Role.permissions`` JSON, aucun nouveau
modèle) :

* ``fpa_saisir``          — saisir le budget de SON département ;
* ``fpa_valider``         — valider/rejeter un budget soumis ;
* ``fpa_consulter_tout``  — voir tous les départements ;
* ``fpa_administrer``     — administration complète FP&A.

WIR173 — ces quatre codes sont désormais ENREGISTRÉS au catalogue
(``apps/roles/models.ALL_PERMISSIONS``, donc assignables depuis l'UI de gestion
des rôles) ET réellement ENFORCÉS : les 14 viewsets FP&A n'avaient AUCUNE garde
(cycles, export XLSX, scénarios, projection de masse salariale étaient ouverts
à tout utilisateur authentifié de la société). ``FpaScopedPermission`` route la
garde par méthode HTTP comme ``core.permissions.ScopedPermission``, à une
différence près : chaque côté accepte un TUPLE de codes (« au moins l'un
d'eux »), parce qu'un module FP&A n'a pas UN code de lecture mais quatre rôles
métier distincts qui lisent tous.

Repli LÉGACY conservé à l'identique du reste du dépôt : un compte SANS rôle fin
garde son accès historique (palier Responsable/Administrateur) — on ne retire
jamais un accès existant.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

FPA_SAISIR = 'fpa_saisir'
FPA_VALIDER = 'fpa_valider'
FPA_CONSULTER_TOUT = 'fpa_consulter_tout'
FPA_ADMINISTRER = 'fpa_administrer'

# Lecture : les quatre rôles métier FP&A consultent (le périmètre par
# département, ci-dessous, décide ENSUITE de ce qu'ils voient).
FPA_LECTURE = (FPA_SAISIR, FPA_VALIDER, FPA_CONSULTER_TOUT, FPA_ADMINISTRER)
# Écriture : ``fpa_consulter_tout`` est un droit de LECTURE élargie, il n'écrit
# jamais.
FPA_ECRITURE = (FPA_SAISIR, FPA_VALIDER, FPA_ADMINISTRER)


def porte_un_code_fpa(user, codes):
    """Vrai si ``user`` porte AU MOINS un des ``codes`` (repli légacy).

    Même sémantique que ``authentication.permissions.HasPermissionOrLegacy``,
    étendue à plusieurs codes : superuser toujours vrai ; compte SANS rôle fin
    → comportement historique (palier Responsable/Administrateur) ; compte AVEC
    rôle fin → il faut réellement porter l'un des codes.
    """
    if not (user and getattr(user, 'is_authenticated', False)):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    role = getattr(user, 'role', None)
    if role is None:
        return bool(getattr(user, 'is_responsable', False))
    return any(user.has_erp_permission(code) for code in codes)


def _codes(valeur):
    """Normalise un ``read_permission``/``write_permission`` en tuple."""
    if not valeur:
        return ()
    if isinstance(valeur, str):
        return (valeur,)
    return tuple(valeur)


class FpaScopedPermission(BasePermission):
    """Garde « lecture ≠ écriture » FP&A, pilotée par le viewset (WIR173).

    Le viewset expose ``read_permission`` / ``write_permission`` (un code ou un
    tuple de codes) ; les méthodes sûres exigent le premier, les autres le
    second. Un côté vide = « authentifié suffit » (aucun viewset FP&A n'est
    dans ce cas, mais la sémantique reste celle de ``ScopedPermission``).
    """

    message = "Accès FP&A refusé : permission fpa_* requise."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe n'atteint jamais une route
        # INTERNE, même en lecture.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        if request.method in SAFE_METHODS:
            codes = _codes(getattr(view, 'read_permission', None))
        else:
            codes = _codes(getattr(view, 'write_permission', None))
        if not codes:
            return True
        return porte_un_code_fpa(user, codes)


def ExigeFpaPermission(*codes):
    """Garde d'``@action`` : exige l'un des ``codes`` FP&A (repli légacy).

    Utilisée sur les actions de GOUVERNANCE d'un cycle budgétaire
    (ouvrir-saisie / clore / dupliquer / export), réservées à
    ``fpa_administrer``.
    """
    class _ExigeFpaPermission(BasePermission):
        message = (
            "Action réservée aux permissions FP&A : " + ', '.join(codes) + '.')

        def has_permission(self, request, view):
            user = getattr(request, 'user', None)
            if not (user and user.is_authenticated):
                return False
            if getattr(user, 'portee', 'interne') != 'interne':
                return False
            return porte_un_code_fpa(user, codes)

    _ExigeFpaPermission.__name__ = 'ExigeFpaPermission_' + '_'.join(codes)
    return _ExigeFpaPermission


def peut_tout_voir(user):
    """Vrai si l'utilisateur voit TOUS les départements.

    Superuser, porteur de ``fpa_consulter_tout``/``fpa_administrer``, ou —
    UNIQUEMENT pour un compte HÉRITÉ sans rôle fin — palier
    Directeur/Administrateur (comportement historique préservé).

    WIR173 : le repli de palier ne s'applique PLUS à un compte portant un rôle
    fin. Sinon ``fpa_saisir`` seul (qui est une permission d'ÉCRITURE, donc
    rend ``CustomUser.is_responsable`` vrai) ouvrirait à son porteur le budget
    de TOUS les départements — exactement le périmètre que NTFPA26 est censé
    fermer.
    """
    if not (user and getattr(user, 'is_authenticated', False)):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'role', None) is not None:
        for code in (FPA_CONSULTER_TOUT, FPA_ADMINISTRER):
            try:
                if user.has_erp_permission(code):
                    return True
            except Exception:
                pass
        return False
    # Repli de palier : Directeur/Administrateur hérités voient tout.
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
