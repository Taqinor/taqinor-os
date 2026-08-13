"""NTEXT31 — SIMULATION (dry-run) d'une règle d'automatisation.

Exécuter une règle pour de vrai est le seul moyen, aujourd'hui, de savoir ce
qu'elle fait — sur un enregistrement réel, avec des emails qui partent. La
simulation répond à la même question SANS AUCUN EFFET : elle DÉCRIT ce que
chaque action ferait (destinataire, champ, valeur, objet créé…) sans jamais
écrire une ligne ni envoyer un message.

Principe de sûreté : la simulation n'appelle JAMAIS un handler d'action. Elle
possède ses propres « descripteurs », qui ne lisent que des helpers PURS de
``actions.py`` (résolution d'email/téléphone, substitution de variables) — un
handler ajouté demain sans descripteur est décrit génériquement, jamais
exécuté.

La séquence multi-étapes (NTEXT4) est parcourue dans l'ordre ; une étape
``WAIT`` (NTEXT7) est décrite comme une suspension et N'INTERROMPT PAS la
description du reste (on montre le plan COMPLET) ; une boucle ``FOR_EACH``
(NTEXT6) résout sa liste en LECTURE SEULE pour dire combien d'itérations elle
ferait.
"""
import logging

logger = logging.getLogger(__name__)

__all__ = ['simuler_regle']


def _label_action(action_type):
    from .models import ActionType

    try:
        return ActionType(action_type).label
    except ValueError:
        return action_type


def _effet(action_type, effet, **details):
    entree = {
        'action_type': action_type,
        'action_label': _label_action(action_type),
        'effet': effet,
    }
    entree.update(details)
    return entree


def _decrire_email(source, instance, company, context):
    from . import actions

    destinataire = actions._resolve_email(instance)
    corps = actions._message_body(source, context)
    if not destinataire:
        return _effet(source.action_type,
                      'Aucune adresse email : rien ne partirait.',
                      destinataire='')
    return _effet(source.action_type,
                  f'Un email partirait à {destinataire}.',
                  destinataire=destinataire, corps=corps)


def _decrire_message(source, instance, company, context):
    from . import actions

    destinataire = actions._resolve_phone(instance)
    corps = actions._message_body(source, context)
    if not destinataire:
        return _effet(source.action_type,
                      'Aucun numéro : rien ne partirait.', destinataire='')
    return _effet(source.action_type,
                  f'Un message partirait au {destinataire}.',
                  destinataire=destinataire, corps=corps)


def _decrire_set_field(source, instance, company, context):
    cfg = source.action_config or {}
    champ = cfg.get('field') or ''
    valeur = cfg.get('value')
    if not champ:
        return _effet(source.action_type, 'Aucun champ configuré.')
    ancienne = getattr(instance, champ, None)
    return _effet(
        source.action_type,
        f'Le champ « {champ} » passerait de « {ancienne} » à « {valeur} ».',
        champ=champ, valeur=valeur, valeur_actuelle=str(ancienne))


def _decrire_assign(source, instance, company, context):
    cfg = source.action_config or {}
    user_id = cfg.get('user_id')
    return _effet(
        source.action_type,
        f"L'enregistrement serait assigné à l'utilisateur {user_id}."
        if user_id else 'Aucun utilisateur configuré.',
        user_id=user_id)


def _decrire_activite(source, instance, company, context):
    from . import actions

    cfg = source.action_config or {}
    corps = actions._substitute_variables(cfg.get('body') or '', context)
    return _effet(source.action_type,
                  'Une activité serait créée.', corps=corps)


def _decrire_ticket(source, instance, company, context):
    cfg = source.action_config or {}
    return _effet(
        source.action_type, 'Un ticket SAV serait créé.',
        type=cfg.get('type', ''), priorite=cfg.get('priorite', ''))


def _decrire_custom_record(source, instance, company, context):
    from . import actions

    cfg = source.action_config or {}
    code = (cfg.get('object_code') or '').strip()
    donnees = cfg.get('data') or {}
    resolues = {
        cle: (actions._substitute_variables(val, context)
              if isinstance(val, str) else val)
        for cle, val in donnees.items()
    } if isinstance(donnees, dict) else {}
    if not code:
        return _effet(source.action_type, 'Aucun objet personnalisé configuré.')
    return _effet(
        source.action_type,
        f'Un enregistrement « {code} » serait créé.',
        object_code=code, donnees=resolues)


def _decrire_wait(source, instance, company, context):
    cfg = source.action_config or {}
    try:
        delai = int(cfg.get('delai_minutes') or 0)
    except (TypeError, ValueError):
        delai = 0
    return _effet(source.action_type,
                  f'La séquence serait suspendue {delai} minute(s), '
                  f'puis reprise.', delai_minutes=delai)


def _decrire_for_each(source, instance, company, context):
    from .list_sources import resolve_list

    cfg = source.action_config or {}
    sous_actions = cfg.get('sous_actions') or []
    elements, tronquee, erreur = resolve_list(
        cfg.get('source'), instance, company, context)
    if erreur:
        return _effet(source.action_type, erreur, iterations=0)
    return _effet(
        source.action_type,
        f'{len(elements)} itération(s) × {len(sous_actions)} sous-action(s) '
        f'seraient exécutées.',
        iterations=len(elements), sous_actions=len(sous_actions),
        tronquee=tronquee)


def _decrire_defaut(source, instance, company, context):
    return _effet(source.action_type,
                  f'Action « {_label_action(source.action_type)} » : '
                  f'aucun détail simulable.')


def _descripteurs():
    from .models import ActionType

    return {
        ActionType.SEND_EMAIL: _decrire_email,
        ActionType.SEND_WHATSAPP: _decrire_message,
        ActionType.SEND_SMS: _decrire_message,
        ActionType.SET_FIELD: _decrire_set_field,
        ActionType.ASSIGN_RECORD: _decrire_assign,
        ActionType.CREATE_ACTIVITY: _decrire_activite,
        ActionType.CREATE_SAV_TICKET: _decrire_ticket,
        ActionType.CREATE_CUSTOM_RECORD: _decrire_custom_record,
        ActionType.WAIT: _decrire_wait,
        ActionType.FOR_EACH: _decrire_for_each,
    }


class _Source:
    """Couple action_type/action_config décrit (règle mono-action ou étape)."""

    __slots__ = ('action_type', 'action_config', 'etape_ordre')

    def __init__(self, action_type, action_config, etape_ordre=None):
        self.action_type = action_type
        self.action_config = action_config or {}
        self.etape_ordre = etape_ordre


def _sources(rule):
    steps = []
    try:
        steps = list(rule.steps.all())
    except Exception:  # pragma: no cover - règle détachée
        steps = []
    if steps:
        return [_Source(s.action_type, s.action_config, s.ordre)
                for s in steps]
    return [_Source(rule.action_type, rule.action_config)]


def simuler_regle(rule, instance, company, *, context=None, user=None,
                  journaliser=True):
    """Décrit CE QUE FERAIT ``rule`` sur ``instance``, sans aucun effet.

    Renvoie la liste des effets prévus (un par action/étape). Quand
    ``journaliser`` est vrai, UNE ligne ``AutomationRun`` de statut
    ``simulation`` est écrite — la seule écriture de toute la simulation, et
    c'est une trace, jamais un effet métier.
    """
    from .models import AutomationRun

    context = context or {}
    descripteurs = _descripteurs()
    effets = []
    for source in _sources(rule):
        descripteur = descripteurs.get(source.action_type, _decrire_defaut)
        try:
            effet = descripteur(source, instance, company, context)
        except Exception as exc:  # jamais de propagation : c'est un dry-run
            logger.warning('simulation: action %s non décrite',
                           source.action_type, exc_info=True)
            effet = _effet(source.action_type,
                           f'Action non simulable : {exc}')
        if source.etape_ordre is not None:
            effet['etape_ordre'] = source.etape_ordre
        effets.append(effet)

    if journaliser:
        try:
            meta = getattr(instance, '_meta', None)
            AutomationRun.objects.create(
                company=company, rule=rule,
                target_model=(f'{meta.app_label}.{meta.model_name}'
                              if meta is not None else ''),
                target_id=getattr(instance, 'pk', None),
                status=AutomationRun.Status.SIMULATION,
                message=f'Simulation : {len(effets)} effet(s) prévu(s).')
        except Exception:  # pragma: no cover - journalisation défensive
            logger.warning('simulation: journalisation impossible',
                           exc_info=True)
    return effets
