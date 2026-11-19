"""Socle des vues `taches` (reference/api.md §0 ; donnees.md invariants 28, 37).

- `PasEncore` : exception (501) LEVÉE par toute route déclarée mais pas encore construite — jamais
  un `return Response(..., status=501)` (la garde des formes le lirait comme la forme de la route).
- `PermissionTaches` : permission STRICTE `user.has_erp_permission('taches_voir')`, jamais le repli
  des comptes sans rôle fin (un compte hérité « responsable » sans rôle reçoit 403). `PERMISSIONS`
  = `[IsAuthenticatedInterne, PermissionTaches]`, posée sur CHAQUE vue.
- `est_assistant(request)` : la requête vient du relais de l'assistant — en-tête
  `X-Taqinor-Assistant` OU authentification `Authorization: Bearer` (échec FERMÉ : le navigateur
  n'envoie que le cookie).
- Les trois routes à jeton (capture, flux, tuile) sont authentifiées par
  `apps.taches.auth_jeton.JetonAccesAuthentication` de leur usage (TCH95). `MethodeAvantJeton` :
  sur ces trois vues, une méthode non servie répond 405 avant l'authentification.
- Outillage de schéma OpenAPI des modules de vues : `forme_echantillon(nom)` (la forme de
  l'`exemple` d'un échantillon de `contract_samples/`), `corps(nom, exemple)`, `reponses(...)`,
  `parametre(...)`, `page_de(...)`.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import APIException, MethodNotAllowed
from rest_framework.parsers import JSONParser
from rest_framework.permissions import BasePermission

from apps.taches.entrees import MOTIF_ANNEE_BORNEE
from authentication.permissions import IsAuthenticatedInterne

DROIT = 'taches_voir'
#: En-tête posé par le relais de l'assistant (`fastapi_ia/.../action_tools.py`, `headers=`).
ENTETE_ASSISTANT = 'X-Taqinor-Assistant'
#: Posé par le front sur la CRÉATION validée au doigt sur une carte du Copilote (acceptation F3, ERR 5).
ENTETE_CARTE_ASSISTANT = 'X-Taqinor-Carte-Assistant'
PREFIXE_BEARER = 'Bearer '
DETAIL_PAS_ENCORE = 'Pas encore construit.'


class PasEncore(APIException):
    """Route déclarée, pas encore construite : 501, levée par la méthode de la vue."""

    status_code = 501
    default_detail = DETAIL_PAS_ENCORE
    default_code = 'pas_encore'


def a_le_droit(user):
    """`taches_voir` porté par le rôle fin (ou superutilisateur) ; AUCUN repli hérité. LA garde du module
    (donnees.md invariant 28) : les routes (`PermissionTaches`) et les envois (`balayage`, la nuit) la
    relisent à chaque appel."""
    return bool(user.has_erp_permission(DROIT))


class PermissionTaches(BasePermission):
    """`taches_voir` porté par le rôle fin (ou superutilisateur) ; AUCUN repli hérité (`a_le_droit`)."""

    message = "Tu n'as pas accès aux tâches."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        return a_le_droit(user)


PERMISSIONS = [IsAuthenticatedInterne, PermissionTaches]
#: Le module ne lit que du JSON (api.md §0 ; écran et relais de l'assistant n'envoient rien d'autre). Déclaré sur
#: chaque vue, le schéma ne publie plus que `application/json` : en formulaire, un `null`, une liste d'entiers ou un
#: objet imbriqué ne se transportent pas, et l'api-fuzz envoyait des corps « conformes » que DRF ne pouvait pas lire
#: (400). Seule exception : `capture/` (raccourci Siri, formulaire possible), qui garde les lecteurs par défaut.
PARSEURS = [JSONParser]


def est_assistant(request):
    """Vrai si la requête vient du relais de l'assistant (en-tête OU Bearer) — échec fermé."""
    entetes = getattr(request, 'headers', {})
    if ENTETE_ASSISTANT in entetes:
        return True
    return (entetes.get('Authorization') or '').startswith(PREFIXE_BEARER)


def carte_assistant(request):
    """Vrai si l'utilisateur valide AU DOIGT, sur son écran, une création proposée par une carte du
    Copilote (`X-Taqinor-Carte-Assistant: 1` exactement ; toute autre valeur est ignorée). Seule la
    `source` de ce qui est créé change (`assistant`, arbitrage A5) : la porte reste l'écran (ses
    validations, sa réponse en clair, aucun masquage, aucun 403) ; ni permission, ni société, ni
    propriétaire, ni confidentialité n'en dépendent. Sous l'en-tête de l'assistant, `est_assistant`
    l'emporte (mode assistant)."""
    return getattr(request, 'headers', {}).get(ENTETE_CARTE_ASSISTANT) == '1'


class MethodeAvantJeton:
    """Mixin des vues à jeton : une méthode que la vue ne sert pas répond 405 AVANT
    l'authentification (api-fuzz « Unsupported methods ») — DRF authentifie avant de chercher le
    gestionnaire, et le refus du jeton rendait 401 à un TRACE. La méthode servie garde son refus
    neutre."""

    def perform_authentication(self, request):
        methode = request.method.lower()
        if methode not in self.http_method_names or not hasattr(self, methode):
            raise MethodNotAllowed(request.method)
        super().perform_authentication(request)


# --- Schémas OpenAPI ---------------------------------------------------------------------------

ECHANTILLONS = Path(__file__).resolve().parent.parent / 'contract_samples'
_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_INSTANT = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:\d{2})$')
_CLE_LIBRE = re.compile(r'^\d+$')
#: nom de composant racine -> échantillon dont il est la forme (lu par tests/test_routes.py).
COMPOSANTS_ECHANTILLON = {}

ERREUR_DETAIL = inline_serializer('TachesErreurDetail', {'detail': serializers.CharField()})
ERREUR_CODE = inline_serializer('TachesErreurCode', {
    'detail': serializers.CharField(), 'code': serializers.CharField()})
#: 400 : `{"<champ>":["message"]}`, ou par ligne / par id (`{"lignes":{"3":{…}}}`).
ERREUR_CHAMPS = {'type': 'object', 'additionalProperties': {},
                 'description': 'Erreurs par champ : {"<champ>": ["message"]} (api.md §0).'}


class _Carte:
    """Objet JSON à clés LIBRES (des ids : `{"53": [...]}`) : une carte, pas des champs."""

    def __init__(self, valeur):
        self.valeur = valeur


def exemple_de(nom):
    """L'`exemple` de `contract_samples/<nom>.json`."""
    return json.loads((ECHANTILLONS / f'{nom}.json').read_text(encoding='utf-8'))['exemple']


def _camel(cle):
    morceaux = [m for m in re.split(r'[^0-9A-Za-z]+', cle) if m]
    return ''.join(m[:1].upper() + m[1:] for m in morceaux) or 'Valeur'


def _fusionner(valeurs):
    """Plusieurs valeurs JSON de même place -> (représentant, nul possible)."""
    nul = any(v is None for v in valeurs)
    presentes = [v for v in valeurs if v is not None]
    if not presentes:
        return None, True
    if all(isinstance(v, dict) for v in presentes):
        if all(_CLE_LIBRE.match(k) for v in presentes for k in v) or not any(presentes):
            return _Carte(_fusionner([x for v in presentes for x in v.values()])), nul
        cles = list(dict.fromkeys(k for v in presentes for k in v))
        return {k: _fusionner([v.get(k) for v in presentes]) for k in cles}, nul
    if all(isinstance(v, list) for v in presentes):
        elements = [x for v in presentes for x in v]
        return ([_fusionner(elements)] if elements else []), nul
    return presentes[0], nul


def _champ_texte(valeur, options):
    if _DATE.match(valeur):
        return serializers.DateField(**options)
    if _INSTANT.match(valeur):
        return serializers.DateTimeField(**options)
    return serializers.CharField(allow_blank=True, **options)


def _champ(noeud, nom, requis=True):
    """Le champ DRF d'un nœud fusionné ; un objet devient un composant nommé `nom`."""
    valeur, nul = noeud
    options = {'allow_null': nul, 'required': requis}
    if valeur is None:
        return serializers.JSONField(**options)
    if isinstance(valeur, bool):
        return serializers.BooleanField(**options)
    if isinstance(valeur, int):
        return serializers.IntegerField(**options)
    if isinstance(valeur, float):
        return serializers.FloatField(**options)
    if isinstance(valeur, str):
        return _champ_texte(valeur, options)
    if isinstance(valeur, _Carte):
        enfant = _champ(valeur.valeur, f'{nom}_Valeur') if valeur.valeur[0] is not None else serializers.JSONField()
        return serializers.DictField(child=enfant, **options)
    if isinstance(valeur, list):
        enfant = _champ(valeur[0], f'{nom}_Element') if valeur else serializers.JSONField()
        return serializers.ListField(child=enfant, **options)
    champs = {cle: _champ(sous, f'{nom}_{_camel(cle)}') for cle, sous in valeur.items()}
    return inline_serializer(nom, champs, **options)


@lru_cache(maxsize=None)
def forme_echantillon(nom):
    """Sérialiseur de schéma (réponse) ayant EXACTEMENT les clés de l'`exemple` de `<nom>.json` —
    même objet à chaque appel (un composant OpenAPI = une identité)."""
    composant = f'TachesEch{_camel(nom)}'
    COMPOSANTS_ECHANTILLON[composant] = nom
    valeur, _ = _fusionner([exemple_de(nom)])
    _nullables(valeur, nuls_de(nom))
    champs = {cle: _champ(sous, f'{composant}_{_camel(cle)}') for cle, sous in valeur.items()}
    return inline_serializer(composant, champs)


#: Clés nulles PARTOUT où elles paraissent (api.md §0) : `geste_id` d'une écriture qui n'a rien changé,
#: `carte_du_moment` d'un écran sans carte. L'exemple n'en montre qu'un cas ; le schéma dit les deux.
TOUJOURS_NULLABLES = ('geste_id', 'carte_du_moment')


def nuls_de(nom):
    """Les chemins (`"plan.planifie_le"`) que `<nom>.json` déclare nuls possibles (`"nuls"`), en plus de ceux
    que l'exemple montre nuls — un exemple ne montre qu'un état (api-fuzz r2 : `null` servi, schéma non nul)."""
    return json.loads((ECHANTILLONS / f'{nom}.json').read_text(encoding='utf-8')).get('nuls', ())


def _nullables(valeur, chemins):
    """Marque nuls possibles les nœuds de `valeur` (fusionné) aux `chemins`, et toute clé de
    `TOUJOURS_NULLABLES`, à toute profondeur."""
    for chemin in chemins:
        noeud, *reste = chemin.split('.')
        cible = valeur
        for morceau in [noeud, *reste][:-1]:
            sous = cible.get(morceau) if isinstance(cible, dict) else None
            cible = sous[0] if sous else None
        dernier = chemin.split('.')[-1]
        if isinstance(cible, dict) and dernier in cible:
            cible[dernier] = (cible[dernier][0], True)
        else:
            raise ValueError(f'nuls : chemin inconnu « {chemin} »')

    def parcourir(noeud):
        if isinstance(noeud, dict):
            for cle, (sous, nul) in list(noeud.items()):
                noeud[cle] = (sous, nul or cle in TOUJOURS_NULLABLES)
                parcourir(sous)
        elif isinstance(noeud, list) and noeud:
            parcourir(noeud[0][0])
        elif isinstance(noeud, _Carte):
            parcourir(noeud.valeur[0])
    parcourir(valeur)


def corps(nom, exemple, requis=()):
    """Sérialiseur de schéma d'un CORPS de requête, déduit d'un corps d'exemple de api.md §4 ;
    seuls les champs `requis` sont obligatoires."""
    valeur, _ = _fusionner([exemple])
    composant = f'TachesCorps{nom}'
    champs = {cle: _champ(sous, f'{composant}_{_camel(cle)}', requis=cle in requis)
              for cle, sous in valeur.items()}
    return inline_serializer(composant, champs)


def reponses(succes, *, statut=200, erreurs=(), conflit=None):
    """Réponses d'une opération : `statut` → `succes`, 401/403 → `{"detail"}`, `erreurs`
    (400 → erreurs par champ, 404/429 → `{"detail"}`), 409 → `conflit`."""
    resultat = {statut: succes, 401: ERREUR_DETAIL, 403: ERREUR_DETAIL}
    for code in erreurs:
        resultat[code] = ERREUR_CHAMPS if code == 400 else ERREUR_DETAIL
    if conflit is not None:
        resultat[409] = conflit
    return resultat


#: Une date reçue en paramètre : `AAAA-MM-JJ` dans la plage de `entrees.DateBornee` (2000 → 2100), publiée.
DATE_BORNEE = {'type': 'string', 'format': 'date', 'pattern': MOTIF_ANNEE_BORNEE}


def parametre(nom, type_=OpenApiTypes.STR, description='', *, enum=None, requis=False):
    """Paramètre de requête (`?nom=`), facultatif sauf `requis` ; `enum` : sa liste fermée publiée. Une date
    publie sa plage d'années (api-fuzz r2 : ce que le schéma déclare valide, le serveur l'accepte)."""
    if type_ == OpenApiTypes.DATE:
        type_ = DATE_BORNEE
    return OpenApiParameter(nom, type_, OpenApiParameter.QUERY, required=requis, description=description,
                            enum=list(enum) if enum is not None else None)


PAGINATION = [parametre('page', OpenApiTypes.INT), parametre('page_size', OpenApiTypes.INT)]


def page_de(nom, enfant):
    """Enveloppe paginée `{"count","next","previous","results"}` (StandardPagination, 50)."""
    return inline_serializer(f'TachesPage{nom}', {
        'count': serializers.IntegerField(),
        'next': serializers.CharField(allow_null=True),
        'previous': serializers.CharField(allow_null=True),
        'results': serializers.ListField(child=enfant),
    })


def liste_de(nom, enfant):
    """Liste à plafond, non paginée : `{"results":[…]}` (api.md §0)."""
    return inline_serializer(f'TachesListe{nom}', {'results': serializers.ListField(child=enfant)})
