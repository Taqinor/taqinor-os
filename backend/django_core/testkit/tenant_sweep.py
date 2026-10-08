"""QAH4 — outillage du balayage d'isolation multi-tenant sur TOUTES les routes.

Le test ``tests/test_tenant_sweep.py`` rejoue, pour CHAQUE viewset monté sous
``api/django/`` (tous les routers DRF du dépôt, pas seulement ceux qui héritent
de ``TenantMixin`` comme le balai YRBAC12 de ``core``), un objet de la société A
avec un utilisateur de la société B. Ce module porte tout ce qui n'est pas une
assertion : la découverte des routes, un constructeur d'objets GÉNÉRIQUE par
modèle, et l'oracle qui décide si une réponse révèle quelque chose.

Trois briques
-------------

* :func:`decouvrir_viewsets` parcourt l'URLconf racine (même technique que
  ``core.tenant_isolation_scan``) et regroupe, par classe de viewset, TOUTES ses
  routes : liste, détail, et chaque ``@action`` (détail ou liste, toute méthode).
  Les routes à suffixe de format (``.json``) sont ignorées : ce sont les mêmes
  vues. Le préfixe ``api/v1/`` est ignoré : c'est la même liste d'apps montée
  une seconde fois (YAPIC7), mêmes classes.

* :class:`Constructeur` fabrique un objet MINIMAL mais RÉEL d'un modèle dans une
  société donnée, sans connaître le modèle : il pose la société, construit
  récursivement les FK obligatoires (dans la MÊME société — un graphe
  multi-tenant cohérent), synthétise une valeur par type de champ et MARQUE
  chaque champ texte d'un jeton propre à la société (``qah4a…`` / ``qah4b…``).
  Ce marqueur est l'oracle le plus large du balai : il suffit qu'il apparaisse
  dans UNE réponse servie à l'autre société (liste, export CSV, statistiques,
  action de liste…) pour que la fuite soit prouvée, quel que soit le chemin.
  Là où ``core.tenant_isolation_scan.build_minimal_instance`` abandonne au
  premier FK obligatoire non trivial (la moitié du parc), celui-ci construit le
  parent.

* :func:`verdict` compare la réponse obtenue sur l'objet du voisin à celle
  obtenue sur un identifiant INEXISTANT. C'est la définition même d'une fuite :
  si la société B ne peut pas distinguer « l'objet de A » de « rien », rien n'a
  fui — un 404 partout, un 403 partout (refus global du rôle) ou un 405 partout
  sont équivalents. Un 2xx sur l'objet de A (lecture/écriture), ou un statut
  différent de celui de l'inexistant (403 contre 404 : l'oracle d'existence que
  la règle « 404, jamais 403 » ferme), est une fuite.

Rien ici n'importe une app métier au niveau module : les modèles sont atteints
par la découverte d'URL elle-même. Jamais importé par du code de production.
"""
from __future__ import annotations

import datetime
import functools
import itertools
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.urls import URLPattern, URLResolver, get_resolver

#: Préfixe balayé : la liste ``_APP_URLS`` de ``erp_agentique/urls.py`` montée
#: sous son préfixe historique. ``api/v1/`` monte EXACTEMENT les mêmes classes.
PREFIXE_BALAYE = 'api/django/'

#: Actions standard d'un ModelViewSet (le reste est une ``@action``).
ACTIONS_STANDARD = frozenset({
    'list', 'create', 'retrieve', 'update', 'partial_update', 'destroy',
})

#: Jetons de marquage (minuscules : la recherche se fait sur le corps abaissé).
MARQUE_A = 'qah4a'
MARQUE_B = 'qah4b'
MARQUE_PARTAGE = 'qah4s'

_RE_GROUPE = re.compile(
    r"\(\?P<(\w+)>(?:[^()]|\([^()]*\))*\)|<(?:\w+:)?(\w+)>")

_COMPTEUR = itertools.count(1)


def _suivant():
    return next(_COMPTEUR)


# ── Découverte ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Route:
    """Une route concrète d'un viewset : un gabarit ``/api/django/x/{pk}/``,
    les groupes qu'il attend, et les méthodes HTTP → action DRF servies."""

    gabarit: str
    groupes: tuple
    methodes: tuple  # ((méthode, action), ...)
    detail: bool

    def remplir(self, valeurs):
        """Chemin appelable, ou ``None`` si un groupe n'a pas de valeur."""
        chemin = self.gabarit
        for nom in self.groupes:
            if nom not in valeurs:
                return None
            chemin = chemin.replace('{' + nom + '}', str(valeurs[nom]))
        return chemin


@dataclass
class EntreeViewSet:
    """Un viewset découvert et toutes ses routes sous ``api/django/``."""

    view_class: type
    initkwargs: dict
    routes: list = field(default_factory=list)

    @property
    def libelle(self):
        return libelle_viewset(self.view_class)

    @property
    def lookup_kwarg(self):
        cls = self.view_class
        return (getattr(cls, 'lookup_url_kwarg', None)
                or getattr(cls, 'lookup_field', None) or 'pk')

    @property
    def lookup_field(self):
        return getattr(self.view_class, 'lookup_field', None) or 'pk'

    def routes_action(self, action):
        """``[(méthode, Route)]`` servant ``action``."""
        return [(m, r) for r in self.routes for m, a in r.methodes
                if a == action]

    def route_liste(self):
        for methode, route in self.routes_action('list'):
            if methode == 'get':
                return route
        return None

    def route_detail(self):
        for methode, route in self.routes_action('retrieve'):
            if methode == 'get':
                return route
        for route in self.routes:
            if route.detail and self.lookup_kwarg in route.groupes and any(
                    a in ACTIONS_STANDARD for _m, a in route.methodes):
                return route
        return None

    def actions_supplementaires(self, detail):
        """``[(méthode, action, Route)]`` des ``@action`` (hors standard).

        Dédupliquées par (méthode, action) : une classe montée sous DEUX
        préfixes (``stock/`` + ``achats/``, ``ventes/`` + ``facturation/`` —
        ODX18/ODX20) sert la même action deux fois, une sonde suffit."""
        out = []
        vues = set()
        for route in self.routes:
            if route.detail != detail:
                continue
            for methode, action in route.methodes:
                if action in ACTIONS_STANDARD or methode in ('head',
                                                             'options'):
                    continue
                if (methode, action) in vues:
                    continue
                vues.add((methode, action))
                out.append((methode, action, route))
        return out


def libelle_viewset(view_class):
    """``app.NomDuViewSet`` — la convention YAPIC2 (stable, lisible en revue).

    ``app`` est le segment après ``apps.`` (ou la racine pour ``core`` /
    ``authentication``). L'unicité est vérifiée par le test statique."""
    module = view_class.__module__
    parts = module.split('.')
    app = parts[1] if parts[0] == 'apps' and len(parts) > 1 else parts[0]
    return f'{app}.{view_class.__name__}'


def _iter_patterns(patterns, prefixe=''):
    for entree in patterns:
        if isinstance(entree, URLResolver):
            yield from _iter_patterns(entree.url_patterns,
                                      prefixe + str(entree.pattern))
        elif isinstance(entree, URLPattern):
            yield prefixe + str(entree.pattern), entree


def _gabarit(route_brute):
    """``api/django/stock/^produits/(?P<pk>[^/.]+)/$`` →
    (``/api/django/stock/produits/{pk}/``, ``('pk',)``)."""
    groupes = []

    def _remplace(m):
        nom = m.group(1) or m.group(2)
        groupes.append(nom)
        return '{' + nom + '}'

    chemin = _RE_GROUPE.sub(_remplace, route_brute)
    chemin = chemin.replace('^', '').replace('$', '')
    chemin = '/' + chemin.lstrip('/')
    chemin = re.sub(r'/+', '/', chemin)
    return chemin, tuple(groupes)


def decouvrir_viewsets(prefixe=PREFIXE_BALAYE):
    """Tous les viewsets DRF montés sous ``prefixe``, dédupliqués par classe,
    triés par libellé (ordre stable = partitions stables)."""
    from rest_framework.viewsets import ViewSetMixin

    par_classe = {}
    for brute, url_pattern in _iter_patterns(get_resolver().url_patterns):
        if not brute.startswith(prefixe):
            continue
        callback = url_pattern.callback
        cls = getattr(callback, 'cls', None)
        if cls is None or not issubclass(cls, ViewSetMixin):
            continue
        gabarit, groupes = _gabarit(brute)
        if 'format' in groupes:
            continue  # suffixe .json : mêmes vues, rien de neuf à sonder
        actions = dict(getattr(callback, 'actions', None) or {})
        initkwargs = dict(getattr(callback, 'initkwargs', None) or {})
        entree = par_classe.get(cls)
        if entree is None:
            entree = par_classe[cls] = EntreeViewSet(
                view_class=cls, initkwargs={
                    k: v for k, v in initkwargs.items()
                    if k in ('basename', 'suffix', 'name', 'description')})
        # ``detail`` vient des routers ; une route montée à la main
        # (``as_view({...})``) ne le porte pas : on le déduit alors de ses
        # actions ou de la présence du segment de recherche dans l'URL.
        detail = bool(initkwargs.get('detail'))
        if not detail and (entree.lookup_kwarg in groupes or any(
                a in ('retrieve', 'update', 'partial_update', 'destroy')
                for a in actions.values())):
            detail = True
        entree.routes.append(Route(
            gabarit=gabarit, groupes=groupes,
            methodes=tuple(sorted(actions.items())), detail=detail))
    return sorted(par_classe.values(), key=lambda e: e.libelle)


def partition(entrees, index, total):
    """La tranche ``index`` sur ``total`` (répartition modulo, stable)."""
    return [e for i, e in enumerate(entrees) if i % total == index]


# ── Modèle servi par un viewset et portée tenant ─────────────────────────────


def modele_statique(view_class):
    """Le modèle servi, lu SANS requête : ``queryset`` de classe puis
    ``serializer_class.Meta.model``. ``None`` si la vue le calcule."""
    qs = getattr(view_class, 'queryset', None)
    if qs is not None:  # jamais ``if qs`` : évaluerait le QuerySet
        return qs.model
    serializer_class = getattr(view_class, 'serializer_class', None)
    meta = getattr(serializer_class, 'Meta', None)
    return getattr(meta, 'model', None)


def instancier_vue(entree, requete_drf, action, kwargs=None):
    """Instance de vue prête à appeler ``get_queryset``/``get_serializer``.
    ``kwargs`` : segments d'URL imbriqués (``object_code``…) que la vue lit."""
    vue = entree.view_class(**entree.initkwargs)
    vue.action = action
    vue.action_map = {}
    vue.request = requete_drf
    vue.args = ()
    vue.kwargs = dict(kwargs or {})
    vue.format_kwarg = None
    vue.headers = {}
    return vue


def requete_drf(user, methode='get', chemin='/'):
    """``rest_framework.request.Request`` authentifiée (sans JWT)."""
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory, force_authenticate

    brute = getattr(APIRequestFactory(), methode)(chemin)
    force_authenticate(brute, user=user)
    from rest_framework.parsers import JSONParser
    return Request(brute, parsers=[JSONParser()])


def modele_dynamique(entree, user):
    """Le modèle via ``get_queryset()`` d'une vue instanciée. Le QuerySet est
    paresseux, mais un ``get_queryset`` peut interroger la base au passage :
    point de sauvegarde, pour qu'un échec n'avorte pas la transaction du test."""
    from django.db import transaction

    try:
        with transaction.atomic():
            vue = instancier_vue(entree, requete_drf(user), 'list')
            qs = vue.get_queryset()
    except Exception:  # noqa: BLE001 — vue calculée : « sans modèle »
        return None
    return getattr(qs, 'model', None)


def _modele_company():
    from authentication.models import Company
    return Company


def _est_company(model):
    return model is not None and model._meta.label_lower == (
        _modele_company()._meta.label_lower)


def _champs_fk_company(model):
    return [f for f in model._meta.concrete_fields
            if f.is_relation and f.related_model is not None
            and _est_company(f.related_model)]


@functools.lru_cache(maxsize=None)
def portee_tenant(model):
    """Comment une ligne de ``model`` appartient à une société.

    * ``'societe'``   — c'est ``authentication.Company`` elle-même ;
    * ``'directe'``   — un FK vers ``Company`` (``company`` d'ordinaire) ;
    * ``'via:<fk>'``  — un FK OBLIGATOIRE vers un modèle lui-même tenant ;
    * ``'via?:<fk>'`` — seulement un FK FACULTATIF vers un modèle tenant (le
      constructeur le renseigne pour rattacher l'objet) ;
    * ``None``        — aucun chemin : référentiel partagé par conception.
    """
    return _portee(model, frozenset())


def _portee(model, pile):
    if model is None:
        return None
    if _est_company(model):
        return 'societe'
    if _champs_fk_company(model):
        return 'directe'
    if model in pile:
        return None
    pile = pile | {model}
    facultatif = None
    for f in model._meta.concrete_fields:
        if not (f.is_relation and f.many_to_one) or f.related_model is None:
            continue
        cible = f.related_model
        if cible is model:
            continue
        if _portee(cible, pile) is None:
            continue
        if not f.null:
            return f'via:{f.name}'
        facultatif = facultatif or f'via?:{f.name}'
    return facultatif


@functools.lru_cache(maxsize=None)
def champs_uniques(model):
    """Noms des champs pris dans une contrainte d'unicité (``unique=True``,
    ``unique_together``, ``UniqueConstraint``) : le constructeur y fait VARIER
    la valeur, sinon le second objet d'une société heurte le premier."""
    from django.db.models import UniqueConstraint

    noms = {f.name for f in model._meta.concrete_fields
            if f.unique and not f.primary_key}
    for groupe in model._meta.unique_together or ():
        noms.update(groupe)
    for contrainte in model._meta.constraints:
        if isinstance(contrainte, UniqueConstraint):
            noms.update(contrainte.fields or ())
    return frozenset(noms)


# ── Constructeur générique ───────────────────────────────────────────────────


class ConstructionImpossible(Exception):
    """Le modèle ne peut pas être construit génériquement (raison en clair)."""


_NOMS_FIN = ('fin', 'end', 'expir', 'echeance', 'cloture', 'jusqu', 'au_')
_NOMS_ANNEE = ('annee', 'year', 'exercice', 'millesime')
_NOMS_MOIS = ('mois', 'month')
_PROFONDEUR_MAX = 7


def _champ_texte(f):
    from django.db import models as m
    return isinstance(f, (m.CharField, m.TextField)) and not f.choices


def _est_obligatoire(f):
    if getattr(f, 'generated', False) or f.primary_key:
        return False
    if getattr(f, 'auto_now', False) or getattr(f, 'auto_now_add', False):
        return False
    return not f.null and not f.has_default()


class Constructeur:
    """Fabrique des objets RÉELS (en base) d'une société, sans connaître le
    modèle. Un constructeur par (société, utilisateur, marque).

    ``objet(model)`` rend une instance NEUVE quand c'est possible (sinon une
    ligne existante de la société : singleton créé par signal, etc.) ;
    ``parent(model)`` rend une instance MISE EN CACHE, réutilisée par tous les
    enfants de la société (un seul client, un seul produit…).
    ``construits[model]`` garde les pk de tout ce qui a été fabriqué ICI.
    """

    def __init__(self, company, user, marque):
        self.company = company
        self.user = user
        self.marque = marque
        self._cache = {}
        self.construits = defaultdict(set)

    # -- valeurs ------------------------------------------------------------

    def marqueur(self, lie=True):
        return f'{self.marque if lie else MARQUE_PARTAGE}{_suivant():05d}'

    def _texte(self, f, lie):
        from django.db import models as m
        max_len = getattr(f, 'max_length', None)
        nom = f.name.lower()
        jeton = self.marqueur(lie)
        if nom == 'cidr' or nom.endswith('_cidr'):
            return '10.0.0.0/8'  # validé au save (identity.IpAllowRule)
        if nom in ('ip', 'adresse_ip') or nom.endswith('_ip'):
            return '10.0.0.1'
        if isinstance(f, m.EmailField) or 'email' in nom:
            valeur = f'{jeton}@example.com'
        elif isinstance(f, m.URLField) or nom in ('url', 'site_web'):
            valeur = f'https://example.com/{jeton}'
        else:
            valeur = jeton
        if max_len and len(valeur) > max_len:
            # Champ trop court pour le marqueur complet : valeur unique courte
            # (base 36), jamais un marqueur tronqué qui ferait un faux oracle.
            valeur = _base36(_suivant())[-max_len:]
        return valeur

    def _scalaire(self, f, lie, varier=False):
        """Valeur triviale mais VALIDE pour ``f``. ``varier`` : le champ est
        pris dans une contrainte d'unicité — chaque appel rend une valeur
        différente (choix suivant, entier suivant, jour précédent)."""
        from django.contrib.postgres.fields import ArrayField
        from django.db import models as m
        from django.utils import timezone

        nom = f.name.lower()
        rang = _suivant() if varier else 0
        if f.choices:
            # ``flatchoices`` aplatit les choix groupés ; on saute un éventuel
            # choix vide (« --- ») qui ne passerait pas une contrainte CHECK.
            valeurs = [v for v, _l in f.flatchoices if v not in ('', None)]
            if valeurs:
                return valeurs[rang % len(valeurs)]
        if isinstance(f, (m.CharField, m.TextField)):
            return self._texte(f, lie)
        if isinstance(f, m.BooleanField):
            return False
        if isinstance(f, (m.FileField,)):
            return f'qah4/{self.marqueur(lie)}.txt'
        if isinstance(f, m.GenericIPAddressField):
            return '127.0.0.1'
        if isinstance(f, m.UUIDField):
            return uuid.uuid4()
        if isinstance(f, m.DecimalField):
            if (f.max_digits or 0) - (f.decimal_places or 0) >= 1:
                return Decimal('1')
            return Decimal('0.1')
        if isinstance(f, m.FloatField):
            return 1.0
        if isinstance(f, m.IntegerField):  # Small/Big/Positive* en héritent
            aujourdhui = timezone.localdate()
            if any(t in nom for t in _NOMS_ANNEE):
                return aujourdhui.year - (rang % 20)
            if any(t in nom for t in _NOMS_MOIS):
                return (aujourdhui.month + rang - 1) % 12 + 1
            return rang or 1
        if isinstance(f, m.DateTimeField):
            maintenant = timezone.now() - datetime.timedelta(days=rang % 3000)
            if any(t in nom for t in _NOMS_FIN):
                return maintenant + datetime.timedelta(days=30)
            return maintenant
        if isinstance(f, m.DateField):
            jour = timezone.localdate() - datetime.timedelta(days=rang % 3000)
            if any(t in nom for t in _NOMS_FIN):
                return jour + datetime.timedelta(days=30)
            return jour
        if isinstance(f, m.TimeField):
            return datetime.time(12, 0)
        if isinstance(f, m.DurationField):
            return datetime.timedelta(hours=1)
        if isinstance(f, m.JSONField):
            return {}
        if isinstance(f, ArrayField):
            return []
        if isinstance(f, m.BinaryField):
            return b''
        type_nom = type(f).__name__
        if type_nom == 'VectorField':
            return [0.0] * int(getattr(f, 'dimensions', None) or 1)
        raise ConstructionImpossible(
            f'type de champ non géré : {f.name} ({type_nom})')

    # -- relations ----------------------------------------------------------

    def _cible_fk(self, f, pile, profondeur, frais=False):
        """Cible d'un FK. ``frais`` : le FK est pris dans une contrainte
        d'unicité (« un profil par client ») — parent NEUF, pas le cache."""
        from django.contrib.auth import get_user_model
        from django.contrib.contenttypes.models import ContentType

        cible = f.related_model
        if _est_company(cible):
            return self.company
        if cible is get_user_model():
            if f.one_to_one or frais:
                return self.utilisateur_neuf()
            return self.user
        if cible is ContentType:
            return ContentType.objects.get_for_model(_modele_company())
        if cible in pile:
            raise ConstructionImpossible(
                f'cycle de FK obligatoires : {f.model.__name__}.{f.name}')
        if f.one_to_one or frais:
            return self._construire(cible, pile, profondeur + 1)
        return self.parent(cible, pile, profondeur + 1)

    def utilisateur_neuf(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(
            username=f'{self.marqueur()}-u', password='x',
            company=self.company, role_legacy='admin')
        self.construits[type(user)].add(user.pk)
        return user

    def parent(self, model, pile=(), profondeur=0):
        """Instance (cache) de ``model`` rattachée à la société."""
        if model in self._cache:
            return self._cache[model]
        instance = self._construire(model, pile, profondeur)
        self._cache[model] = instance
        return instance

    def objet(self, model):
        """Instance NEUVE de ``model`` (repli : ligne existante)."""
        return self._construire(model, (), 0)

    # -- construction -------------------------------------------------------

    def _existante(self, model):
        """Ligne déjà présente de la société (singleton posé par un signal)."""
        champs = _champs_fk_company(model)
        if not champs:
            return None
        return model._base_manager.filter(
            **{champs[0].name: self.company}).order_by('pk').first()

    def _construire(self, model, pile, profondeur):
        from django.contrib.auth import get_user_model
        from django.db import transaction

        if _est_company(model):
            self.construits[model].add(self.company.pk)
            return self.company
        if model is get_user_model():
            return self.utilisateur_neuf()
        if profondeur > _PROFONDEUR_MAX:
            raise ConstructionImpossible(
                f'graphe de FK trop profond ({model.__name__})')
        if model._meta.abstract:
            raise ConstructionImpossible(f'modèle abstrait : {model.__name__}')
        pile = tuple(pile) + (model,)
        derniere = None
        # Trois essais : (1) riche, parents du cache, premières valeurs ;
        # (2) riche, mais les champs pris dans une contrainte d'unicité
        # VARIENT (parent neuf, choix/entier/jour suivant) — le second objet
        # d'une société ne heurte plus le premier ; (3) minimal (champs
        # obligatoires seuls) si un champ facultatif rempli dérangeait.
        # Puis, si une contrainte CHECK a refusé la ligne (« exactement une
        # cible », « lead OU client », « produit XOR catégorie » — mesurés sur
        # le balai YRBAC12), un essai par FK FACULTATIF renseigné seul.
        essais = [(True, False, frozenset()), (True, True, frozenset()),
                  (False, True, frozenset())]
        check_vu = False
        rang = 0
        while rang < len(essais):
            riche, variante, forcer = essais[rang]
            rang += 1
            # Un point de sauvegarde annulé efface AUSSI les parents construits
            # pendant l'essai : le cache ne doit jamais garder une instance dont
            # la ligne n'existe plus (FK fantôme → IntegrityError plus loin).
            cache_avant = dict(self._cache)
            construits_avant = {k: set(v) for k, v in self.construits.items()}
            try:
                with transaction.atomic():
                    instance = self._instancier(model, pile, profondeur,
                                                riche, variante, forcer)
                    instance.save()
            except Exception as exc:  # noqa: BLE001 — essai suivant/repli
                self._cache = cache_avant
                self.construits = defaultdict(set, construits_avant)
                if not forcer or derniere is None:
                    # Le rapport garde la cause des essais DE BASE : l'échec
                    # d'un essai « un FK forcé » est un effet, pas la cause.
                    derniere = exc
                if isinstance(exc, ConstructionImpossible) and not forcer:
                    break  # même cause en mode minimal : droit au repli
                if not check_vu and 'check constraint' in str(exc):
                    check_vu = True
                    essais += [(True, True, frozenset({nom}))
                               for nom in _fk_facultatifs(model)]
                continue
            self.construits[model].add(instance.pk)
            return instance
        # Repli : un singleton par société (OneToOne company, ligne posée par
        # un signal à la création de la société, contrainte « un seul actif »)
        # refuse un second exemplaire — une ligne RÉELLE de la société, déjà
        # en cache ou en base, reste un objet légitime à rejouer chez le voisin.
        existante = self._cache.get(model)
        if existante is None:
            try:
                with transaction.atomic():
                    existante = self._existante(model) or (
                        model._base_manager.filter(
                            pk__in=self.construits.get(model, ()))
                        .order_by('pk').first())
            except Exception:  # noqa: BLE001 — pas de repli possible
                existante = None
        if existante is not None:
            self.construits[model].add(existante.pk)
            return existante
        if isinstance(derniere, ConstructionImpossible):
            raise derniere
        premiere_ligne = (str(derniere).splitlines() or [''])[0][:200]
        raise ConstructionImpossible(
            f'{model._meta.label} : {type(derniere).__name__}: '
            f'{premiere_ligne}')

    def _instancier(self, model, pile, profondeur, riche, variante,
                    forcer=frozenset()):
        from django.contrib.auth import get_user_model

        portee = portee_tenant(model)
        lie = portee is not None
        uniques = champs_uniques(model)
        valeurs = {}
        for f in model._meta.concrete_fields:
            if f.primary_key and (f.auto_created
                                  or type(f).__name__.endswith('AutoField')):
                continue
            if getattr(f, 'generated', False):
                continue
            if f.is_relation:
                if f.related_model is None:
                    continue
                if _est_company(f.related_model):
                    valeurs[f.name] = self.company  # même nullable : rattaché
                    continue
                obligatoire = not f.null
                rattache = (portee or '').startswith('via?:') and (
                    portee.split(':', 1)[1] == f.name)
                utilisateur = f.related_model is get_user_model()
                # Essai « forcé » : SEUL le FK visé s'ajoute aux obligatoires
                # (pas les FK utilisateur facultatifs du mode riche, qui
                # peuvent eux-mêmes être des cibles de la contrainte XOR).
                if obligatoire or rattache or f.name in forcer or (
                        riche and utilisateur and not f.one_to_one
                        and not forcer):
                    valeurs[f.name] = self._cible_fk(
                        f, pile, profondeur,
                        frais=variante and f.name in uniques)
                continue
            if f.primary_key:
                if not f.has_default():
                    valeurs[f.name] = self._scalaire(f, lie, varier=True)
                continue
            if _champ_texte(f) and not f.has_default():
                # Texte libre : marqué en mode riche (l'oracle « marqueur »
                # en dépend) ; en mode minimal, seulement s'il est exigé
                # (``blank=False``) ou unique — un « » vide passe sinon.
                if riche or not f.blank or f.name in uniques:
                    valeurs[f.name] = self._texte(f, lie)
                continue
            if _est_obligatoire(f):
                valeurs[f.name] = self._scalaire(
                    f, lie, varier=variante and f.name in uniques)
        # GenericForeignKey obligatoire : pointer la société elle-même.
        for f in model._meta.concrete_fields:
            if f.name == 'object_id' and 'content_type' in valeurs:
                valeurs[f.name] = self.company.pk
        return model(**valeurs)


#: Nombre maximal d'essais « un FK facultatif à la fois » (contrainte CHECK).
_ESSAIS_XOR_MAX = 6


def _fk_facultatifs(model):
    """FK FACULTATIFS candidats à un essai « renseigné seul » : ni société,
    ni auto-référence ; les cibles tenant d'abord (une contrainte « exactement
    une cible » vise d'ordinaire des objets métier), bornés."""
    candidats = [
        f for f in model._meta.concrete_fields
        if f.is_relation and f.many_to_one and f.null
        and f.related_model is not None and f.related_model is not model
        and not _est_company(f.related_model)]
    candidats.sort(key=lambda f: portee_tenant(f.related_model) is None)
    return [f.name for f in candidats[:_ESSAIS_XOR_MAX]]


def _base36(n):
    chiffres = '0123456789abcdefghijklmnopqrstuvwxyz'
    out = ''
    while True:
        n, r = divmod(n, 36)
        out = chiffres[r] + out
        if not n:
            return out


# ── Lecture des réponses et oracle ───────────────────────────────────────────


_TYPES_TEXTE = ('json', 'text', 'csv', 'xml', 'javascript', 'html')


def corps_texte(reponse):
    """Corps abaissé si textuel (JSON, CSV, HTML…), sinon ``''`` (PDF, XLSX
    et autres binaires compressés : le marqueur n'y est pas lisible)."""
    type_contenu = (reponse.get('Content-Type') or '').lower()
    if type_contenu and not any(t in type_contenu for t in _TYPES_TEXTE):
        return ''
    try:
        if getattr(reponse, 'streaming', False):
            brut = b''.join(reponse.streaming_content)
        else:
            brut = reponse.content
    except Exception:  # noqa: BLE001 — corps illisible : aucun oracle
        return ''
    try:
        return brut.decode('utf-8', errors='replace').lower()
    except AttributeError:
        return str(brut).lower()


def contient_marque(reponse, marque):
    return marque in corps_texte(reponse)


def lignes(data):
    """Lignes d'une réponse liste (paginée ``{results}`` ou liste nue)."""
    if isinstance(data, dict) and isinstance(data.get('results'), list):
        data = data['results']
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return None


def identifiants_lignes(data, cles=('id', 'pk')):
    rangs = lignes(data)
    if rangs is None:
        return None
    ids = set()
    for rang in rangs:
        for cle in cles:
            if cle in rang and rang[cle] is not None:
                ids.add(str(rang[cle]))
    return ids


def _succes(statut):
    return 200 <= statut < 300


@dataclass(frozen=True)
class Constat:
    """Une fuite prouvée : ``genre`` ∈ lecture | ecriture | existence |
    creation, ``cle`` = identifiant stable pour le cliquet ``FUITES_CONNUES``."""

    libelle: str
    genre: str
    sonde: str  # ex. "GET retrieve", "POST valider", "GET list (marqueur)"
    detail: str

    @property
    def cle(self):
        return f'{self.libelle} :: {self.sonde}'


def a_besoin_de_la_sonde_absente(statut_objet):
    """Faut-il rejouer la requête sur un identifiant INEXISTANT ? Non quand
    l'objet du voisin répond déjà 404 : c'est la réponse idéale, rien à
    comparer (et une requête de moins par sonde, sur des centaines)."""
    return statut_objet != 404


def verdict(methode, statut_objet, statut_absent, marque_dans_corps):
    """Genre de fuite — ``'lecture'``, ``'ecriture'``, ``'existence'`` — ou
    ``None``.

    ``statut_absent`` est le statut servi à la MÊME requête sur un identifiant
    qui n'existe pas (``None`` si elle n'a pas été jouée). La règle : la société
    B ne doit pas pouvoir distinguer l'objet de A du néant.
    """
    if statut_objet == 404:
        return None
    if statut_objet == 429 or statut_absent == 429:
        return None  # limitation de débit : aucune information exploitable
    if _succes(statut_objet):
        if statut_absent is not None and _succes(statut_absent):
            # La vue ignore l'identifiant (singleton, agrégat de la société de
            # l'appelant) : fuite seulement si des données de A sont servies.
            return 'lecture' if marque_dans_corps else None
        return 'lecture' if methode.lower() == 'get' else 'ecriture'
    if statut_absent is not None and statut_objet != statut_absent:
        return 'existence'
    return None


def donnees(reponse):
    """Données d'une réponse : ``.data`` DRF, sinon JSON décodé, sinon None."""
    data = getattr(reponse, 'data', None)
    if data is not None:
        return data
    if 'json' not in (reponse.get('Content-Type') or '').lower():
        return None
    if getattr(reponse, 'streaming', False):
        return None
    try:
        import json
        return json.loads(reponse.content)
    except Exception:  # noqa: BLE001
        return None


#: Fragments de nom d'``@action`` de LISTE dont la réponse est binaire (PDF,
#: tableur zippé, image) : le marqueur n'y est pas lisible, les appeler ne
#: prouverait rien et coûterait un rendu WeasyPrint. Les actions de DÉTAIL, elles,
#: sont toujours sondées : leur oracle est le STATUT, pas le corps.
FRAGMENTS_BINAIRES = ('pdf', 'xlsx', 'etiquette', 'image', 'avatar')


def action_binaire(action):
    nom = action.lower()
    return any(fragment in nom for fragment in FRAGMENTS_BINAIRES)


def valeur_groupe(instance, groupe):
    """Valeur d'un segment d'URL IMBRIQUÉ (``object_code``, ``devis_pk``…)
    déduite d'un FK de ``instance`` ; ``None`` si rien de sûr (la route est
    alors comptée « non sondée », jamais devinée)."""
    for suffixe, attribut in (('_code', 'code'), ('_slug', 'slug'),
                              ('_pk', 'pk'), ('_id', 'pk')):
        if groupe.endswith(suffixe):
            break
    else:
        return None
    prefixe = groupe[:-len(suffixe)]
    candidats = []
    for f in type(instance)._meta.concrete_fields:
        if not (f.is_relation and f.many_to_one) or f.related_model is None:
            continue
        if attribut != 'pk' and not any(
                c.name == attribut
                for c in f.related_model._meta.concrete_fields):
            continue
        candidats.append(f)
    choisis = [f for f in candidats if f.name == prefixe
               or f.name.startswith(prefixe) or prefixe.startswith(f.name)]
    if not choisis and attribut != 'pk' and len(candidats) == 1:
        choisis = candidats
    if len(choisis) != 1:
        return None
    parent = getattr(instance, choisis[0].name, None)
    if parent is None:
        return None
    return getattr(parent, attribut, None)


_RE_MARQUE_B = re.compile(MARQUE_B + r'\d{5}')


def charge_utile(serializer, instance):
    """Corps de création rejouable, dérivé d'une instance RÉELLE via les
    champs INSCRIPTIBLES du sérialiseur (même chemin que DRF :
    ``get_attribute`` puis ``to_representation``). Les marqueurs de la
    société B sont renouvelés pour ne pas heurter une contrainte d'unicité."""
    from django.db import transaction
    from rest_framework import serializers as drf

    corps = {}
    for nom, champ in serializer.fields.items():
        if champ.read_only or isinstance(
                champ, (drf.HiddenField, drf.BaseSerializer, drf.FileField)):
            continue
        try:
            # Point de sauvegarde par champ : un attribut calculé qui
            # interroge la base et échoue n'avorte pas la transaction du test.
            with transaction.atomic():
                attribut = champ.get_attribute(instance)
                valeur = (None if attribut is None
                          else champ.to_representation(attribut))
        except Exception:  # noqa: BLE001 — champ calculé : on s'en passe
            continue
        if valeur is None and not getattr(champ, 'allow_null', False):
            continue
        if isinstance(valeur, str):
            valeur = _RE_MARQUE_B.sub(
                lambda _m: f'{MARQUE_B}{_suivant():05d}', valeur)
        corps[nom] = valeur
    return corps


def valeur_absente(model, lookup_field):
    """Un identifiant qui n'existe pas (même type que la clé de recherche)."""
    from django.db import models as m
    try:
        champ = model._meta.pk if lookup_field == 'pk' else (
            model._meta.get_field(lookup_field))
    except Exception:  # noqa: BLE001
        return 987654321
    if isinstance(champ, m.UUIDField):
        return uuid.uuid4()
    if isinstance(champ, (m.CharField, m.SlugField, m.TextField)):
        return 'qah4-inexistant'
    return 987654321


# ── ASEC18 — étape « écriture » : FK inscriptible vers l'objet du voisin ─────
#
# Le balai ci-dessus rejoue l'objet de A avec l'utilisateur de B (lecture,
# PATCH, DELETE). Il ne voyait pas l'autre sens de la fuite (C-ASEC-007) : A
# écrit SUR SON PROPRE OBJET l'identifiant d'une ligne de B dans une FK
# inscriptible (``assigned_to``, ``client``, ``produit``…). Le sérialiseur DRF
# accepte toute clé primaire de la table cible ; la ligne de B est alors liée
# à un document de A et son libellé lui est souvent renvoyé. Ces briques
# énumèrent ces FK et jugent la relecture ; l'orchestration est dans
# ``tests/test_tenant_sweep.py``.


def champs_fk_inscriptibles(serializer):
    """``[(nom, source, modele_cible, multiple)]`` — relations par clé
    primaire INSCRIPTIBLES du sérialiseur vers un modèle tenant (hors
    ``Company`` elle-même, déjà sondée par l'étape « company étrangère »).

    Un champ dont la cible ne se résout pas sans requête (``get_queryset``
    surchargé qui échoue) ou dont la source est imbriquée (``a.b``) est
    ignoré : jamais deviné."""
    from django.db import transaction
    from rest_framework import relations

    out = []
    for nom, champ in serializer.fields.items():
        if getattr(champ, 'read_only', False):
            continue
        multiple = isinstance(champ, relations.ManyRelatedField)
        relation = champ.child_relation if multiple else champ
        if not isinstance(relation, relations.PrimaryKeyRelatedField):
            continue
        source = getattr(champ, 'source', None)
        if not source or source == '*' or '.' in source:
            continue
        queryset = getattr(relation, 'queryset', None)
        if queryset is None:
            try:
                with transaction.atomic():
                    queryset = relation.get_queryset()
            except Exception:  # noqa: BLE001 — cible non résoluble
                continue
        cible = getattr(queryset, 'model', None)
        if cible is None or _est_company(cible) or portee_tenant(cible) is None:
            continue
        out.append((nom, source, cible, multiple))
    return out


def valeur_relation(instance, source):
    """Valeur RELUE EN BASE de la relation ``source`` de ``instance`` :
    l'identifiant (FK) ou l'ensemble des identifiants (M2M). Lève si
    ``source`` n'est pas un champ du modèle."""
    model = type(instance)
    champ = model._meta.get_field(source)
    frais = model._base_manager.get(pk=instance.pk)
    if champ.many_to_many:
        return frozenset(getattr(frais, source).values_list('pk', flat=True))
    return getattr(frais, champ.attname)


def fk_voisine_ecrite(valeur, pk_voisin):
    """Vrai si la relation relue POINTE la ligne du voisin."""
    if isinstance(valeur, (set, frozenset, list, tuple)):
        return any(str(v) == str(pk_voisin) for v in valeur)
    return valeur is not None and str(valeur) == str(pk_voisin)


def site_serialiseur(serializer, nom):
    """Site au format de ``scripts/fk_scoping_allow.txt`` :
    ``backend/django_core/<module>.py::Serializer.champ``."""
    cls = type(serializer)
    chemin = 'backend/django_core/' + cls.__module__.replace('.', '/') + '.py'
    return f'{chemin}::{cls.__name__}.{nom}'


METHODES_ECRITURE = ('post', 'put', 'patch')


def decouvrir_apiviews_ecriture(prefixe=PREFIXE_BALAYE):
    """Les APIView / ``@api_view`` (HORS viewsets) montées sous ``prefixe`` qui
    acceptent une écriture : ``[(libellé, gabarit, (méthodes,))]`` trié.

    Elles n'ont ni ``queryset`` ni sérialiseur déclaratif fiables : le balai
    ne sait pas les exercer génériquement, mais il les COMPTE dans les sites
    d'écriture (rapport) au lieu de les ignorer en silence."""
    from rest_framework.views import APIView
    from rest_framework.viewsets import ViewSetMixin

    vus = {}
    for brute, url_pattern in _iter_patterns(get_resolver().url_patterns):
        if not brute.startswith(prefixe):
            continue
        cls = getattr(url_pattern.callback, 'cls', None)
        if cls is None or not issubclass(cls, APIView) or issubclass(
                cls, ViewSetMixin):
            continue
        gabarit, groupes = _gabarit(brute)
        if 'format' in groupes:
            continue
        methodes = tuple(m for m in METHODES_ECRITURE if hasattr(cls, m))
        if not methodes:
            continue
        vus.setdefault((libelle_viewset(cls), gabarit), methodes)
    return sorted((lib, gab, meth) for (lib, gab), meth in vus.items())
