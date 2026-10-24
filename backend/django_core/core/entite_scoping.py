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
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.relations import PrimaryKeyRelatedField

import logging

logger = logging.getLogger(__name__)

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

    Une valeur absente ou vide vaut « pas de filtre ». CI #997 — une valeur
    non entière (``?entite=null``, ``abc``) répond 400 nommant le paramètre,
    comme le schéma ``integer`` le déclare (elle était ignorée en silence) ;
    jamais une erreur 500.
    """
    if request is None:
        return None
    params = getattr(request, 'query_params', None)
    if params is None:
        return None
    from core.champs_stricts import entier_ou_400
    return entier_ou_400(params.get('entite'), 'entite')


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


def _assert_entite_de_la_societe(user, entite_id, inconnu_404=False):
    """ASEC7 — lève ``ValidationError`` (400, champ ``entite``) si l'entité
    ``entite_id`` n'est pas une entité de la société de ``user`` ;
    ``NotFound`` (404, MÊME corps) quand ``inconnu_404`` — la surface dont le
    sérialiseur porte ``IdInconnu404Mixin`` (devis : ``client``/``lead``
    répondent 404) ne doit pas faire de ``entite`` l'exception à 400.

    Sans société de référence (superuser plateforme, appel hors requête) :
    aucune vérification, comme le scoping de lecture. Lecture du modèle par
    ``apps.get_model`` — ``core`` n'importe aucune app."""
    company_id = getattr(user, 'company_id', None)
    if company_id is None:
        return
    from django.apps import apps as django_apps
    try:
        Entite = django_apps.get_model('entites', 'Entite')
    except LookupError:  # app entités absente : rien à rattacher
        return
    if not Entite.objects.filter(pk=entite_id, company_id=company_id).exists():
        # ENF17 — UNE seule réponse : celle du champ ``entite`` borné à la
        # société (ACAL298, ``SameCompanyFKSerializerMixin``), c.-à-d. l'erreur
        # « objet inexistant » de DRF, code ``does_not_exist``. Ce filet de vue
        # répond AVANT le sérialiseur ; avec un texte propre (code ``invalid``)
        # il faisait de l'entité étrangère deux réponses selon la couche.
        gabarit = PrimaryKeyRelatedField.default_error_messages['does_not_exist']
        detail = {'entite': [str(gabarit).format(pk_value=entite_id)]}
        if inconnu_404:
            raise NotFound(ValidationError(detail, code='does_not_exist').detail)
        raise ValidationError(detail, code='does_not_exist')


def assert_entite_assignable(user, entite_id, *, inconnu_404=False):
    """NTADM3 — lève ``PermissionDenied`` (403) si ``user`` n'a pas le droit
    de rattacher une ligne à l'entité ``entite_id``.

    Une valeur vide (« non affecté ») est TOUJOURS autorisée ; une valeur non
    numérique est laissée au serializer (400), jamais transformée en 403.
    """
    if entite_id in (None, '', 'null'):
        return
    try:
        valeur = int(entite_id)
    except (TypeError, ValueError):
        return
    # ASEC7 — l'entité doit appartenir à la société de l'utilisateur, MÊME
    # quand son rôle ne porte aucun périmètre (``entites_visibles_ids`` =
    # None) : avant, ce cas rendait la main sans rien vérifier et une entité
    # d'une AUTRE société était acceptée. 400 sur ``entite``, réponse
    # identique pour un id étranger et un id inexistant (aucun oracle).
    _assert_entite_de_la_societe(user, valeur, inconnu_404=inconnu_404)
    ids = entites_visibles_ids(user)
    if ids is None:
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
    #: ENF17 — vrai sur un viewset dont le sérialiseur d'écriture porte
    #: ``IdInconnu404Mixin`` : l'entité inconnue/étrangère répond alors 404
    #: comme ses autres FK (sinon 400, réponse historique des factures).
    entite_inconnue_404 = False

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
        # CI #997 api-fuzz : une méthode que la route ne porte pas (``action``
        # nul — ex. PUT sur une @action POST seule) est un 405 : le contrôle
        # d'entité ne doit pas répondre 400/403 à sa place.
        if hasattr(self, 'action') and self.action is None:
            return
        try:
            data = request.data
        except Exception:  # noqa: BLE001 — corps illisible : le parseur DRF (D-ENF22-BLE001)
            logger.warning("initial : échec ignoré, comportement dégradé", exc_info=True)
            return           # de la vue tranchera (400/415), jamais un 500 ici
        if not hasattr(data, 'get') or self.entite_field not in data:
            return
        assert_entite_assignable(request.user, data.get(self.entite_field),
                                 inconnu_404=self.entite_inconnue_404)
