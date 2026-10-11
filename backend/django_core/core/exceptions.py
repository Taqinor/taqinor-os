"""YAPIC3 — enveloppe d'erreur DRF unifiée via un `EXCEPTION_HANDLER` global.

Sans ceci, les 400 (dict field-keyed DRF natif), 401/403 (``{"detail": …}``),
404 et 500 ont des formes DIFFÉRENTES et aucun code machine stable n'existe
pour qu'un client (frontend, intégration) distingue les cas sans parser un
message humain. ``taqinor_exception_handler`` délègue D'ABORD au handler DRF
natif (jamais de logique de statut HTTP dupliquée) PUIS reformate la réponse
dans une forme UNIQUE :

    {"error": {"code": "<slug stable>", "message": "<humain FR>",
               "fields": {<champ>: [<msgs>]}, "request_id": "<id>"}}

``code`` est dérivé de la classe d'exception (jamais du message, qui peut
changer) ; ``fields`` n'apparaît QUE pour les 400 de validation (dict
field-keyed). ``request_id`` est lu depuis ``request.request_id`` (posé par
``core.middleware.RequestIdMiddleware``, YAPIC4) — ``None`` tant que ce
middleware n'est pas monté, jamais une erreur.

Une exception NON gérée par DRF (``exception_handler`` renvoie ``None``) est
elle aussi enveloppée ici en 500 ``server_error`` — le SEUL endroit qui
transforme une exception Python arbitraire en JSON, pour que 100% des
réponses d'erreur DRF (y compris les crashs) portent la même forme.

``django.db.models.ProtectedError`` (bug user-visible, 2026-07-31) reçoit un
traitement DÉDIÉ dans ce même seau « non géré par DRF » : plusieurs FK
``on_delete=PROTECT`` protègent désormais une preuve financière/légale
(``RegulatoryDossier.devis``, ``SubventionDossier.devis``,
``PaiementFacturePortail.facture``, ``AcceptationDevisPortail.devis``…) et le
refus de suppression est CORRECT — mais sans ce traitement, il remontait en
500 générique au lieu d'un 409 explicite. Centralisé ICI (plutôt que dans
chaque viewset) pour que TOUT app en bénéficie sans y penser ; ne RÉGRESSE
jamais ``apps.crm``/``apps.stock`` qui interceptent DÉJÀ ``ProtectedError``
localement dans leur ``destroy()`` et renvoient leur propre ``Response`` —
cette branche ne voit donc que les ``ProtectedError`` qu'AUCUNE vue n'a
attrapées (ex. ``apps.ventes`` Devis/Facture, qui n'avaient aucun override).
"""
from __future__ import annotations

import logging
import re
import uuid

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.fields import get_error_detail
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

from core.parametres_requete import MESSAGE_CHAMP as MESSAGE_PARAMETRE_INCONNU
from core.parametres_requete import ParametresRequeteInconnus
from core.unicite import ConflitUnicite, decrire_contrainte, message_conflit

logger = logging.getLogger(__name__)

# Slug stable par classe d'exception DRF — jamais dérivé du message humain
# (qui peut être traduit/reformulé sans casser un client qui teste `code`).
_CODE_BY_EXCEPTION = (
    # ENF2 (C3) — DRF convertit ``django.http.Http404`` en ``NotFound`` et
    # ``django.core.exceptions.PermissionDenied`` en ``PermissionDenied`` AVANT
    # de construire la réponse, mais c'est l'exception D'ORIGINE qui arrive
    # ici : sans ces deux lignes, chaque ``get_object_or_404`` (4 018 cas au
    # fuzz du 07/10) répondait 404 avec ``code: "server_error"`` et « Une
    # erreur inattendue s'est produite ».
    (Http404, 'not_found'),
    (DjangoPermissionDenied, 'permission_denied'),
    (ConflitUnicite, 'unique_conflict'),
    # ENFP (D1) — paramètre de requête non déclaré au schéma OpenAPI.
    (ParametresRequeteInconnus, 'unknown_query_parameter'),
    (drf_exceptions.ValidationError, 'validation_error'),
    (drf_exceptions.AuthenticationFailed, 'not_authenticated'),
    (drf_exceptions.NotAuthenticated, 'not_authenticated'),
    (drf_exceptions.PermissionDenied, 'permission_denied'),
    (drf_exceptions.NotFound, 'not_found'),
    (drf_exceptions.Throttled, 'throttled'),
    (drf_exceptions.MethodNotAllowed, 'method_not_allowed'),
    (drf_exceptions.NotAcceptable, 'not_acceptable'),
    (drf_exceptions.UnsupportedMediaType, 'unsupported_media_type'),
    (drf_exceptions.ParseError, 'parse_error'),
)


def _code_for(exc) -> str:
    for exc_class, code in _CODE_BY_EXCEPTION:
        if isinstance(exc, exc_class):
            return code
    if isinstance(exc, drf_exceptions.APIException):
        return 'api_error'
    return 'server_error'


def _message_for(exc, code: str) -> str:
    """Message humain FR — stable et générique par code (jamais le détail
    brut DRF, qui peut fuiter des informations internes sur un 500)."""
    if code == 'server_error':
        return "Une erreur inattendue s'est produite."
    if isinstance(exc, Http404):
        # Le message Django (« No Devis matches the given query. ») est en
        # anglais et nomme le modèle interne : jamais repris dans l'enveloppe.
        return MESSAGE_NOT_FOUND
    if isinstance(exc, DjangoPermissionDenied):
        return str(exc) or MESSAGE_PERMISSION_DENIED
    detail = getattr(exc, 'detail', None)
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return str(detail[0])
    if isinstance(detail, dict):
        # Vue générale — le détail par champ va dans `fields`, pas ici.
        non_field = detail.get('non_field_errors') or detail.get('detail')
        if non_field:
            return str(non_field[0] if isinstance(non_field, list) else non_field)
    return str(exc)


def _fields_for(exc, code: str):
    """`fields` pour les 400 de validation avec un detail field-keyed (dict),
    pour les 409 ``unique_conflict`` (champs de la contrainte) et pour les 400
    ``unknown_query_parameter`` (paramètres refusés) — jamais pour les autres
    codes."""
    if code == 'unique_conflict':
        return _champs_conflit(getattr(exc, 'champs', None))
    if code == 'unknown_query_parameter':
        return {nom: [MESSAGE_PARAMETRE_INCONNU]
                for nom in getattr(exc, 'parametres', [])} or None
    if code != 'validation_error':
        return None
    detail = getattr(exc, 'detail', None)
    if not isinstance(detail, dict):
        return None
    fields = {}
    for key, value in detail.items():
        if key == 'non_field_errors':
            continue
        fields[key] = value if isinstance(value, list) else [value]
    return fields or None


MESSAGE_NOT_FOUND = 'Ressource introuvable.'
MESSAGE_PERMISSION_DENIED = (
    "Vous n'avez pas la permission d'effectuer cette action.")
MESSAGE_CHAMP_EN_DOUBLE = 'Cette valeur existe déjà.'
# SQLSTATE Postgres d'une violation d'unicité (psycopg2 `pgcode`).
_SQLSTATE_UNIQUE = '23505'


_METHODES_ECRITURE = frozenset({'POST', 'PUT', 'PATCH'})


def _methode(context) -> str:
    request = context.get('request') if context else None
    return str(getattr(request, 'method', '') or '').upper()


def _champs_conflit(champs):
    if not champs:
        return None
    return {champ: [MESSAGE_CHAMP_EN_DOUBLE] for champ in champs}


def _violation_unicite(exc):
    """(modèle, champs) si ``exc`` est une violation d'unicité Postgres,
    sinon None. Lecture du SQLSTATE sur la cause pilote (psycopg2 ``pgcode``,
    psycopg 3 ``sqlstate``) — jamais du message."""
    if not isinstance(exc, IntegrityError):
        return None
    cause = exc.__cause__
    sqlstate = (getattr(cause, 'pgcode', None)
                or getattr(cause, 'sqlstate', None))
    if sqlstate != _SQLSTATE_UNIQUE:
        return None
    diag = getattr(cause, 'diag', None)
    return decrire_contrainte(
        getattr(diag, 'constraint_name', None),
        table=getattr(diag, 'table_name', None),
        detail=getattr(diag, 'message_detail', None))


def _unique_violation_response(model, champs, request_id) -> Response:
    """ENF2 (C6) — filet de sécurité : la contrainte d'unicité en base a
    refusé l'écriture (course entre deux requêtes, ou vue hors
    ``TenantMixin`` donc sans pré-validation ``core.unicite``). C'est un
    conflit de données, pas un crash : 409 ``unique_conflict`` nommé, MÊME
    forme que la pré-validation. La transaction de requête éventuelle
    (ATOMIC_REQUESTS) est marquée pour annulation, comme DRF le fait pour
    ses propres exceptions."""
    set_rollback()
    champs = list(champs or [])
    message = (message_conflit(model, champs) if model is not None
               else ConflitUnicite.default_detail)
    body = {
        'detail': message,
        'error': {
            'code': 'unique_conflict',
            'message': message,
            'fields': _champs_conflit(champs),
            'request_id': request_id,
        },
    }
    return Response(body, status=status.HTTP_409_CONFLICT)


def _request_id(context) -> str | None:
    request = context.get('request') if context else None
    return getattr(request, 'request_id', None) if request is not None else None


def _request_id_garanti(context) -> str:
    """Identifiant de corrélation d'un 500 — TOUJOURS une chaîne (ACAL315).

    Normalement posé par ``core.middleware.RequestIdMiddleware``. S'il manque
    (middleware non monté, requête construite à la main), un ``uuid4`` est
    généré ICI et reposé sur la requête, pour que l'enveloppe, l'en-tête
    ``X-Request-Id`` et la ligne de journal portent le MÊME id — jamais
    ``null`` (live PUB : « request_id null in the shell »)."""
    request = context.get('request') if context else None
    request_id = _request_id(context)
    if request_id:
        return str(request_id)
    request_id = uuid.uuid4().hex
    if request is not None:
        for cible in (getattr(request, '_request', None), request):
            if cible is None:
                continue
            try:
                cible.request_id = request_id
            except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
                pass
    return request_id


def _journalise_500(exc, context, request_id: str) -> None:
    """ACAL315 — un 500 n'est JAMAIS muet : pile + request_id + chemin +
    méthode + société dans le journal. Jamais le corps ni un en-tête (aucun
    secret). Lecture réflexive de la société : `core` n'importe aucune app."""
    request = context.get('request') if context else None
    path = getattr(request, 'path', None)
    method = getattr(request, 'method', None)
    user = getattr(request, 'user', None)
    company_id = getattr(user, 'company_id', None) if user is not None else None
    logger.exception(
        '500 non géré [request_id=%s] %s %s (société=%s) : %s',
        request_id, method, path, company_id, type(exc).__name__,
        exc_info=exc,
        extra={'request_id': request_id, 'path': path,
               'company_id': company_id, 'method': method},
    )


def _protected_error_message(exc: ProtectedError) -> str:
    """Message FR expliquant CE qui bloque encore la suppression.

    ``exc.protected_objects`` (posé par Django) porte les instances dont le
    FK ``on_delete=PROTECT`` pointe vers l'enregistrement qu'on essaie de
    supprimer — on les regroupe par modèle (``verbose_name``) pour un message
    lisible sans jamais importer le modèle concerné (générique, réflexif :
    `core` reste une couche foundation qui n'importe aucune app domaine)."""
    par_modele: dict[str, int] = {}
    for obj in getattr(exc, 'protected_objects', None) or []:
        meta = getattr(obj, '_meta', None)
        label = str(getattr(meta, 'verbose_name', None) or type(obj).__name__)
        par_modele[label] = par_modele.get(label, 0) + 1
    if par_modele:
        details = ', '.join(
            f'{count} {label}' for label, count in par_modele.items())
        return (
            'Suppression refusée : cet enregistrement est encore référencé '
            f'par {details}. Supprimez ou détachez d\'abord ces éléments '
            'avant de réessayer.'
        )
    return (
        'Suppression refusée : cet enregistrement est encore référencé par '
        "d'autres données (preuve financière ou légale conservée)."
    )


def _protected_error_response(exc: ProtectedError, request_id: str | None) -> Response:
    """409 clair pour un ``ProtectedError`` non intercepté par la vue.

    Forme cohérente avec le reste du module : ``detail`` à la racine (même
    clé que les 401/403/404 DRF natifs, et que le pattern déjà en place dans
    ``apps.crm``/``apps.stock`` pour leurs propres 409 « objet référencé ») +
    l'enveloppe machine ``error`` (YAPIC3) pour les clients qui testent
    ``code`` plutôt qu'un message humain."""
    message = _protected_error_message(exc)
    body = {
        'detail': message,
        'error': {
            'code': 'protected_error',
            'message': message,
            'fields': None,
            'request_id': request_id,
        },
    }
    return Response(body, status=status.HTTP_409_CONFLICT)


def _rate_limit_headers_for(exc, context):
    """YAPIC12 — X-RateLimit-Limit/X-RateLimit-Remaining sur un 429. Ne
    RE-DÉCLENCHE jamais ``allow_request`` (mutation de l'état du throttle,
    ex. compteur cache) : lecture STATIQUE de la config de débit du premier
    throttle scopé de la vue seulement — best-effort, jamais bloquant."""
    if not isinstance(exc, drf_exceptions.Throttled):
        return {}
    view = context.get('view') if context else None
    if view is None or not hasattr(view, 'get_throttles'):
        return {}
    try:
        for throttle in view.get_throttles():
            rate = getattr(throttle, 'rate', None) or (
                throttle.get_rate() if hasattr(throttle, 'get_rate') else None)
            if not rate:
                continue
            num_requests, _duration = throttle.parse_rate(rate)
            return {
                'X-RateLimit-Limit': str(num_requests),
                'X-RateLimit-Remaining': '0',
            }
    except Exception:  # noqa: BLE001 — advisory headers, never break the 429
        pass
    return {}


# ENF1b — message EXACT de ``IntegerField.get_prep_value`` (Django) quand
# une recherche ORM reçoit un identifiant non numérique fourni par le client
# (« null,null », « {} », « AAA »…). Seul CE message est reconnu : un
# ``ValueError`` quelconque reste un 500 (bug serveur, jamais masqué).
_ID_NON_NUMERIQUE = re.compile(
    r"^Field '(?P<champ>[^']+)' expected a number but got (?P<valeur>.*)\.$",
    re.S)


def _kwargs_url(context) -> dict:
    vue = context.get('view') if context else None
    return dict(getattr(vue, 'kwargs', None) or {})


def _exception_client(exc, context):
    """ENF1b (api-fuzz du 09/10 : 18 des 29 « Server error ») — deux erreurs
    Django qui signalent une ENTRÉE CLIENT invalide, pas un bug serveur, et
    que DRF ne sait pas traduire (son handler renvoie ``None`` → 500) :

    * ``django.core.exceptions.ValidationError`` (``full_clean()``, ou
      ``Field.to_python`` sur une valeur brute passée au modèle) → 400
      ``validation_error``, détail par champ conservé ;
    * le ``ValueError`` « Field 'id' expected a number but got … » d'une
      recherche ORM sur un identifiant non numérique → 404 ``not_found``
      quand la valeur est un paramètre de CHEMIN (comme
      ``get_object_or_404`` de DRF, qui attrape déjà ce cas), sinon 400.

    Renvoie l'exception DRF équivalente, ou ``None`` (exception inchangée).
    """
    if isinstance(exc, DjangoValidationError):
        return drf_exceptions.ValidationError(detail=get_error_detail(exc))
    if type(exc) is ValueError:
        trouve = _ID_NON_NUMERIQUE.match(str(exc))
        if trouve is None:
            return None
        valeur = trouve.group('valeur')
        if any(repr(v) == valeur or repr(str(v)) == valeur
               for v in _kwargs_url(context).values()):
            return drf_exceptions.NotFound()
        return drf_exceptions.ValidationError({
            trouve.group('champ'): [
                f'Identifiant invalide : {valeur} (nombre entier attendu).'],
        })
    return None


def _corps_liste_en_objet(response) -> None:
    """ENF1b — ``raise ValidationError('…')`` produit un corps LISTE
    (``["…"]``) : ni le schéma ``ErreurApi`` (un objet) ni le frontend
    (``lib/apiError.js`` lit ``detail``/``non_field_errors``) ne le
    comprennent. On le replie en objet ``{detail, non_field_errors}``."""
    if isinstance(response.data, list):
        messages = [str(m) for m in response.data]
        response.data = {
            'detail': messages[0] if messages else '',
            'non_field_errors': messages,
        }


def taqinor_exception_handler(exc, context):
    """`REST_FRAMEWORK['EXCEPTION_HANDLER']` — enveloppe UNIQUE pour toute
    réponse d'erreur DRF, y compris les exceptions non reconnues par DRF
    (repliées en 500 `server_error`)."""
    traduite = _exception_client(exc, context)
    if traduite is not None:
        exc = traduite
    response = drf_exception_handler(exc, context)
    request_id = _request_id(context)

    if response is None:
        # ``ProtectedError`` (django.db.models) n'est pas une APIException
        # DRF : `drf_exception_handler` renvoie None pour elle comme pour
        # tout bug applicatif. Elle a SA propre branche (409 explicite,
        # jamais un 500) — voir le docstring du module en tête de fichier.
        if isinstance(exc, ProtectedError):
            return _protected_error_response(exc, request_id)
        # Une violation d'unicité n'est un CONFLIT client que sur une
        # écriture demandée par le client (POST/PUT/PATCH). Sur une lecture
        # ou une suppression, c'est un bug serveur (ex. amorçage paresseux qui
        # recrée une ligne) : il reste un 500 journalisé, jamais masqué.
        violation = _violation_unicite(exc)
        if violation is not None and _methode(context) in _METHODES_ECRITURE:
            return _unique_violation_response(*violation, request_id)
        # Exception non gérée par DRF (ex. bug applicatif) — la forme
        # unifiée reste due même ici ; le statut HTTP/sémantique tenant ne
        # change JAMAIS (toujours 500, jamais masqué en 200).
        code = 'server_error'
        request_id = _request_id_garanti(context)
        _journalise_500(exc, context, request_id)
        body = {
            'error': {
                'code': code,
                'message': _message_for(exc, code),
                'fields': None,
                'request_id': request_id,
            },
        }
        response = Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Même id dans l'en-tête (le middleware le réécrit à l'identique
        # quand il est monté ; sans lui, l'en-tête reste quand même posé).
        response['X-Request-Id'] = request_id
        return response

    code = _code_for(exc)
    if code == 'validation_error':
        _corps_liste_en_objet(response)
    envelope = {
        'code': code,
        'message': _message_for(exc, code),
        'fields': _fields_for(exc, code),
        'request_id': request_id,
    }
    # YAPIC3 — enveloppe ADDITIVE, jamais un remplacement de corps. On CONSERVE
    # la forme DRF native au niveau racine (dict field-keyed pour un 400,
    # ``{"detail": …}`` pour 401/403/404) — sinon on casse TOUT consommateur
    # existant (frontend + ~centaines de tests) qui lit ``resp.data['<champ>']``
    # ou ``resp.data['detail']`` — et on expose EN PLUS l'enveloppe machine
    # stable sous la clé ``error`` (code/message/fields/request_id). Un champ de
    # validation littéralement nommé ``error`` (rarissime) est préservé tel quel.
    if isinstance(response.data, dict):
        response.data.setdefault('error', envelope)
    # Corps non-dict (rare) : laissé intact pour la rétro-compatibilité ; le
    # request_id reste disponible via l'en-tête X-Request-Id (YAPIC4).
    for header, value in _rate_limit_headers_for(exc, context).items():
        response[header] = value
    return response
