"""Portée « entité » (Groupe NTADM) — filtre d'affichage + périmètre de rôle.

Deux mécanismes DISTINCTS, volontairement séparés :

* **NTADM2 — filtre de CONFORT** (``?entite=<id>``) : un paramètre de requête
  OPTIONNEL qui restreint une liste à une entité (``apps.entites``). Il
  n'accorde ni ne retire aucun droit ; absent, la liste est STRICTEMENT celle
  d'aujourd'hui.

* **NTADM3 — périmètre de DONNÉES par rôle** (``Role.entites_visibles``) :
  un narrowing OPT-IN, exactement le patron déjà en place pour
  ``records_scope_*`` (cf. ``core.scoping``). Un rôle SANS aucune entité
  visible voit TOUT — c'est l'état de tous les comptes existants, donc zéro
  régression. Dès qu'il en porte au moins une, la liste devient une LISTE
  BLANCHE :
    - les lignes ``entite IS NULL`` (« non affecté ») restent visibles de
      tous — elles n'appartiennent à aucune filiale ;
    - les lignes rattachées à une entité HORS périmètre disparaissent des
      listes ET du détail (404, jamais 403 : aucun oracle d'existence) ;
    - créer/modifier une ligne vers une entité hors périmètre est REFUSÉ
      (403).

``core`` reste une couche de FONDATION : ce module n'importe AUCUNE app (le
périmètre se lit via ``user.role.entites_visibles``, une simple traversée
d'ORM, jamais un import de ``apps.roles``/``apps.entites``).
"""
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

__all__ = [
    'entite_id_demandee',
    'filtre_entite_demandee',
    'entites_visibles_ids',
    'scope_entite_queryset',
    'assert_entite_assignable',
    'EntiteScopeMixin',
]


def entite_id_demandee(request):
    """``?entite=<id>`` normalisé en entier, ou ``None``.

    Une valeur absente, vide ou non numérique vaut « pas de filtre » — jamais
    une erreur 500 ni une liste vide surprise.
    """
    if request is None:
        return None
    params = getattr(request, 'query_params', None)
    if params is None:
        return None
    brut = params.get('entite')
    if brut in (None, ''):
        return None
    try:
        return int(brut)
    except (TypeError, ValueError):
        return None


def filtre_entite_demandee(qs, request, champ='entite'):
    """NTADM2 — applique le filtre OPTIONNEL ``?entite=<id>`` sur ``qs``.

    Additif : sans le paramètre, ``qs`` est renvoyé INCHANGÉ. La société est
    déjà filtrée en amont (``TenantMixin``) — on n'ajoute jamais un
    re-filtrage société ici.
    """
    entite_id = entite_id_demandee(request)
    if entite_id is None:
        return qs
    return qs.filter(**{f'{champ}_id': entite_id})


def entites_visibles_ids(user):
    """NTADM3 — ids des entités visibles par ``user``, ou ``None``.

    ``None`` (et non un ensemble vide) quand aucune restriction ne s'applique :
    « pas de périmètre » et « périmètre vide » sont deux états distincts, et
    seul le premier existe côté données (même convention que
    ``core.scoping.visible_user_ids`` et ``roles.cles_apps_autorisees``).

    Aucune restriction pour : un anonyme, un superuser, un compte sans rôle
    fin (légacy), ou un rôle dont ``entites_visibles`` est vide — c'est-à-dire
    absolument TOUS les comptes existants aujourd'hui.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    if getattr(user, 'is_superuser', False):
        return None
    role = getattr(user, 'role', None)
    if role is None:
        return None
    ids = set(role.entites_visibles.values_list('id', flat=True))
    return ids or None


def scope_entite_queryset(qs, user, champ='entite'):
    """NTADM3 — restreint ``qs`` au périmètre d'entités de ``user``.

    Renvoie ``qs`` INCHANGÉ quand le rôle ne porte aucun périmètre. Sinon :
    lignes « non affectées » (``entite IS NULL``) + lignes des entités
    visibles. La société est déjà filtrée en amont (``TenantMixin``) — on
    n'ajoute jamais un re-filtrage société ici.
    """
    ids = entites_visibles_ids(user)
    if ids is None:
        return qs
    return qs.filter(
        Q(**{f'{champ}_id__isnull': True}) | Q(**{f'{champ}_id__in': ids}))


def assert_entite_assignable(user, entite_id):
    """NTADM3 — lève ``PermissionDenied`` (403) si ``user`` n'a pas le droit
    de rattacher une ligne à l'entité ``entite_id``.

    Une valeur vide (« non affecté ») est TOUJOURS autorisée ; une valeur non
    numérique est laissée au serializer (400), jamais transformée en 403.
    """
    if entite_id in (None, '', 'null'):
        return
    ids = entites_visibles_ids(user)
    if ids is None:
        return
    try:
        valeur = int(entite_id)
    except (TypeError, ValueError):
        return
    if valeur not in ids:
        raise PermissionDenied("Cette entité est hors de votre périmètre.")


class EntiteScopeMixin:
    """Mixin de ViewSet : filtre optionnel ``?entite=`` (NTADM2) + périmètre
    de données par rôle (NTADM3), sans toucher aux permissions de l'hôte.

    À poser AVANT la base scopée société dans les bases de la classe ::

        class DevisViewSet(EntiteScopeMixin, CompanyScopedModelViewSet):

    ``get_queryset`` compose avec ``super()`` : le scoping société reste en
    amont et INCHANGÉ. Sans ``?entite=`` et sans périmètre de rôle, le
    queryset rendu est byte-identique à celui d'avant.

    ``initial`` refuse (403) une écriture qui rattacherait la ligne à une
    entité hors périmètre. Le contrôle est posé là — et non dans
    ``perform_create`` — parce que plusieurs viewsets hôtes surchargent
    ``perform_create``/``create`` sans appeler ``super()``, et parce qu'un
    ``get_permissions`` propre à l'hôte ignore silencieusement le
    ``permission_classes`` d'une ``@action``.
    """

    #: nom du champ FK vers ``entites.Entite`` sur le modèle du viewset.
    entite_field = 'entite'

    def get_queryset(self):
        qs = super().get_queryset()
        request = getattr(self, 'request', None)
        if request is None:
            return qs
        qs = scope_entite_queryset(
            qs, getattr(request, 'user', None), self.entite_field)
        return filtre_entite_demandee(qs, request, self.entite_field)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ('POST', 'PUT', 'PATCH'):
            return
        try:
            data = request.data
        except Exception:  # noqa: BLE001 — corps illisible : le parseur DRF
            return           # de la vue tranchera (400/415), jamais un 500 ici
        if not hasattr(data, 'get') or self.entite_field not in data:
            return
        assert_entite_assignable(request.user, data.get(self.entite_field))
