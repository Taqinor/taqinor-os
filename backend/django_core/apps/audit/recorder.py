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

Quel journal pour quoi (ARC16 — entonnoir unique de journalisation)
-------------------------------------------------------------------

Quatre mécanismes de journalisation SE RECOUVRENT dans le repo ; ce module est
l'entonnoir de FAIT pour le couple « trace d'audit + chatter » d'un changement
de champ. Carte de décision :

* ``apps.audit`` (``AuditLog`` via ``recorder.record``) — le journal d'audit
  INTERNE unique (réservé au Directeur) : QUI a fait QUOI et QUAND, sur TOUS les
  objets. C'est ici.
* ``apps.records`` (``records.Activity`` via ``records.services.log_activity``)
  — le « chatter » générique visible dans la fiche de l'objet (le « mail.thread »
  maison, ARC8) : la timeline lisible par l'utilisateur métier.
* ``record_field_change`` (ci-dessous) — l'ENTONNOIR : pour un changement de
  champ, écrit l'``AuditLog`` ET (si demandé) la ligne de chatter
  ``modification`` en UN SEUL appel, au lieu de deux appels séparés qui divergent.
* ``apps.parametres.models_audit.SettingsAuditLog`` et
  ``apps.compta.models.PisteAuditComptable`` restent des SATELLITES de
  conformité intentionnels (journal des réglages ; piste d'audit comptable
  légale) : ils NE sont PAS fusionnés ici — une éventuelle fusion serait une
  DECISION future hors périmètre. FG18 nomme le satellite « réglages » pour la
  complétude.
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


def record_field_change(instance, field, old, new, *, user=_UNSET,
                        field_label='', company=None, action=None,
                        chatter=True, detail=None):
    """Entonnoir unique (ARC16) : journalise un changement de champ en UN appel.

    Écrit l'``AuditLog`` (via ``record``, avec un diff structuré
    ``changes=[{"field", "old", "new"}]``) ET — si ``chatter`` — la ligne de
    chatter ``modification`` correspondante (``records.services.log_activity``).
    Remplace le patron « deux appels séparés » (un audit + un chatter) qui
    divergeaient. ``action`` par défaut = STATUS pour un champ nommé ``statut`` /
    ``status`` / ``etat`` / ``stage`` / ``etape``, sinon UPDATE.

    Best-effort de bout en bout : chaque branche est indépendante et n'élève
    JAMAIS (même contrat que ``record`` et que le chatter existant) — un audit ou
    un chatter qui échoue ne casse ni l'autre ni la requête de l'utilisateur.

    Args:
        instance: instance métier modifiée (sa société/CT/repr en sont dérivés).
        field: nom technique du champ modifié (ex. ``'statut'``).
        old / new: valeurs avant / après (converties en texte pour l'affichage).
        user: acteur ; défaut = acteur courant (résolu depuis la requête).
        field_label: libellé humain du champ pour le chatter (ex. ``'Statut'``).
        company: société explicite ; par défaut déduite de ``instance``.
        action: ``AuditLog.Action`` explicite ; sinon STATUS/UPDATE auto.
        chatter: si ``False``, n'écrit QUE l'``AuditLog`` (pour un appelant qui
            gère déjà son propre chatter applicatif — évite un doublon).
        detail: libellé d'audit explicite ; sinon composé « label : old → new »
            (permet à un appelant de conserver un texte 1:1 à l'identique).
    """
    old_txt = '' if old is None else str(old)
    new_txt = '' if new is None else str(new)

    if action is None:
        from .models import AuditLog
        status_like = (field or '').lower() in (
            'statut', 'status', 'etat', 'état', 'stage', 'etape', 'étape')
        action = AuditLog.Action.STATUS if status_like else AuditLog.Action.UPDATE

    label = field_label or field or ''
    if detail is None:
        detail = f'{label} : « {old_txt} » → « {new_txt} »' if label else \
            f'« {old_txt} » → « {new_txt} »'

    # Branche 1 — trace d'audit (best-effort, gérée dans record()).
    record(
        action, instance=instance, company=company, user=user,
        detail=detail,
        changes=[{'field': field or '', 'old': old_txt, 'new': new_txt}])

    # Branche 2 — chatter « modification » (best-effort, indépendant).
    if chatter:
        try:
            from apps.records.services import log_field_change
            act_user = current_user() if user is _UNSET else user
            log_field_change(
                instance, field, old_txt, new_txt, user=act_user,
                field_label=field_label, company=company)
        except Exception:  # noqa: BLE001 — best-effort, ne jamais bloquer
            logger.debug('audit chatter mirror failed', exc_info=True)
