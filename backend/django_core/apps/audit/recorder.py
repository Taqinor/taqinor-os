"""Capture best-effort du Journal d'activité (Feature G).

Conception : un thread-local porte la requête courante (posée par
``AuditActorMiddleware``). Les signaux CRUD ne journalisent QUE pendant une
requête — les écritures ORM directes (migrations, seed, tests sans requête) ne
produisent donc aucune ligne, ce qui évite tout bruit et toute interférence.
L'acteur est résolu PARESSEUSEMENT depuis ``request.user`` : DRF ne renseigne
l'utilisateur (JWT) qu'au moment de la vue, après le middleware — on lit donc
``request.user`` au moment où le signal se déclenche (dans la vue), pas avant.

``record`` n'élève JAMAIS : toute erreur est avalée pour ne jamais casser ni
bloquer la requête de l'utilisateur (même esprit que le « chatter » existant).
"""
import logging
import threading

logger = logging.getLogger(__name__)
_state = threading.local()
_UNSET = object()  # sentinelle : « user non fourni » ≠ « user=None » (système)


def begin_request(request):
    _state.request = request


def end_request():
    _state.request = None


def current_request():
    return getattr(_state, 'request', None)


def current_user():
    req = current_request()
    user = getattr(req, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    return None


def in_request():
    return current_request() is not None


def _company_of(instance):
    """Société d'une instance : champ direct, sinon via ``produit``."""
    company = getattr(instance, 'company', None)
    if company is not None:
        return company
    produit = getattr(instance, 'produit', None)
    return getattr(produit, 'company', None)


def record(action, *, instance=None, content_type=None, object_id=None,
           object_repr=None, detail='', company=None, user=_UNSET,
           actor_username=None, changes=None):
    """Écrit une ligne d'audit. Best-effort : aucune exception ne remonte.

    Si ``instance`` est fourni, content_type/object_id/object_repr/company en
    sont dérivés (sauf surcharge explicite). ``user`` par défaut = acteur courant
    (résolu depuis la requête) ; passer ``user=None`` pour une action système.

    ``changes`` (YHARD3, optionnel) — diff structuré best-effort pour les
    UPDATE : liste de ``{"field": ..., "old": ..., "new": ...}``. Purement
    additif ; ``None`` par défaut (comportement inchangé). Consommé par
    ``selectors.reconstruct_as_of`` pour rejouer l'état d'un objet à une date
    passée."""
    try:
        from django.contrib.contenttypes.models import ContentType
        from .models import AuditLog

        if user is _UNSET:
            user = current_user()

        ct = content_type
        if instance is not None:
            if ct is None:
                ct = ContentType.objects.get_for_model(instance.__class__)
            if object_id is None:
                object_id = str(getattr(instance, 'pk', '') or '')
            if object_repr is None:
                try:
                    object_repr = str(instance)
                except Exception:
                    object_repr = ''
            if company is None:
                company = _company_of(instance)

        # La société de l'acteur prime quand l'instance n'en porte pas.
        if company is None and user is not None:
            company = getattr(user, 'company', None)

        if actor_username is None:
            actor_username = getattr(user, 'username', '') or ''

        AuditLog.objects.create(
            company=company,
            user=user if (user and getattr(user, 'is_authenticated', False))
            else None,
            actor_username=actor_username,
            action=action,
            content_type=ct,
            object_id=str(object_id or '')[:64],
            object_repr=(object_repr or '')[:255],
            detail=detail or '',
            changes=changes,
        )
    except Exception:  # noqa: BLE001 — best-effort, ne jamais bloquer la requête
        logger.debug('audit record failed', exc_info=True)
