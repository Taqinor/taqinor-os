"""NTI18N40 — permission fine « gérer la localisation et les traductions ».

LE PROBLÈME : jusqu'ici, tout l'écran Paramètres → Localisation (langue de
repli NTI18N34, verrou de langue d'interface NTI18N35, fuseau d'affichage
NTOBS23, assistant pays NTI18N31, fêtes mobiles NTI18N33) et l'écran
Traductions (N94) étaient gouvernés par le PALIER de menu
(``IsAdminOrResponsableTier``) et par ``parametres_modifier`` — le même droit
qui ouvre la tarification, les modèles de documents et les référentiels. Une
société ne pouvait donc pas confier la relecture linguistique à quelqu'un sans
lui ouvrir au passage tous les réglages de la société, ni retirer la
localisation à un rôle qui doit garder le reste des paramètres.

CE CODE : ``localisation_gerer``, un code de plus au catalogue
``roles.ALL_PERMISSIONS`` — donc porté par défaut par Directeur et
Administrateur (qui en DÉRIVENT) et ajouté à ``RESPONSABLE_PERMISSIONS`` pour
que le palier Responsable garde EXACTEMENT l'accès qu'il avait. Aucun accès
existant n'est retiré ; ce qui devient possible, c'est de DÉCOCHER la
localisation sur un rôle personnalisé sans toucher à ``parametres_modifier``.

FORME DU CODE : underscore (``localisation_gerer``), jamais une notation
pointée. ``CustomUser.has_erp_permission`` compare la chaîne au contenu de
``Role.permissions`` : un code pointé ne matche jamais rien et rend la garde
silencieusement inerte (le défaut mesuré par WIR11 sur les règles SoD).

PORTÉE : garde SERVEUR des endpoints de localisation/traductions. Le masquage
de l'onglet côté interface consomme le même code (``state.auth.permissions``,
déjà acheminé au front) — le câblage de l'écran vit hors de cette lane.

LECTURE NON RESTREINTE, ET C'EST VOULU : ``TranslationOverrideViewSet.list``
est chargé AU LOGIN par tous les rôles pour fusionner les surcharges par-dessus
les catalogues statiques N93 (cf. sa docstring). La borner ferait afficher à
un commercial une interface non traduite. La garde porte donc sur les ÉCRITURES
de traduction et sur les endpoints de localisation.
"""
from authentication.permissions import HasPermissionOrLegacy

#: Code de permission ERP (catalogue ``apps.roles.models.ALL_PERMISSIONS``).
PERMISSION_LOCALISATION_GERER = 'localisation_gerer'

#: Classe de permission DRF prête à poser dans ``permission_classes``.
#: ``HasPermissionOrLegacy`` (et non ``HasPermission``) : un compte HÉRITÉ sans
#: rôle fin garde son comportement historique — on ne retire jamais un accès
#: en ajoutant un code au catalogue.
PeutGererLocalisation = HasPermissionOrLegacy(PERMISSION_LOCALISATION_GERER)


def peut_gerer_localisation(user) -> bool:
    """Le porteur peut-il gérer localisation/traductions ?

    Même décision que ``PeutGererLocalisation``, utilisable hors d'une requête
    DRF (sérialiseur, sélecteur, tâche). Jamais d'exception : un ``user``
    absent ou anonyme renvoie ``False``.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'role', None):
        return user.has_erp_permission(PERMISSION_LOCALISATION_GERER)
    return bool(getattr(user, 'is_responsable', False))
