"""Exécution des actions d'automatisation (N72).

Chaque fonction renvoie ``(status, message)`` (status ∈ AutomationRun.Status).
Les envois RÉUTILISENT les canaux existants et restent SANS EFFET (statut
``noop`` journalisé) quand le canal n'est pas configuré — jamais d'échec dur ni
de dépendance externe nouvelle. Aucun prix d'achat ni marge n'est exposé.

``action_config`` (JSON libre) pilote chaque action, par ex. :
  - send_* :   {'template': 'devis_unique', 'langue': 'fr'} ou {'body': '...'}
  - set_field: {'field': 'priorite', 'value': 'haute'}
  - assign:    {'user_id': 12}  (assigne owner/technicien selon le modèle)
  - activity:  {'body': 'Rappeler le client'}
  - sav_ticket:{'type': 'preventif', 'priorite': 'normale', 'description': '...'}
"""
import logging

from django.conf import settings

from .models import ActionType, AutomationRun, CanalMessage, ModeleMessage

logger = logging.getLogger(__name__)

Status = AutomationRun.Status


def run(rule, instance, company, context, user):
    """Aiguille vers le handler d'action. Best-effort, ne lève pas."""
    handler = _HANDLERS.get(rule.action_type)
    if handler is None:
        return Status.SKIPPED, f'Action inconnue : {rule.action_type}'
    try:
        return handler(rule, instance, company, context or {}, user)
    except Exception as exc:  # pragma: no cover - filet de sécurité
        logger.exception('automation: action %s échouée', rule.action_type)
        return Status.FAILED, str(exc)


# ── Envois (réutilisent les canaux existants, no-op si non configurés) ──────

def _resolve_phone(instance):
    for attr in ('whatsapp', 'telephone'):
        val = getattr(instance, attr, None)
        if val:
            return val
    client = getattr(instance, 'client', None)
    if client is not None:
        for attr in ('whatsapp', 'telephone'):
            val = getattr(client, attr, None)
            if val:
                return val
    return None


def _resolve_email(instance):
    val = getattr(instance, 'email', None)
    if val:
        return val
    client = getattr(instance, 'client', None)
    if client is not None:
        return getattr(client, 'email', None)
    return None


class _SafeDict(dict):
    """Dict tolérant pour ``str.format_map`` : une clé absente reste littérale
    (``{inconnue}``) au lieu de lever ``KeyError`` — les corps existants sans
    aucune variable (immense majorité) restent rendus À L'IDENTIQUE."""

    def __missing__(self, key):
        return '{' + key + '}'


def _substitute_variables(body, context):
    """Substitue les variables ``{var}`` du corps depuis ``context`` (XPRJ23).

    ``context`` peut porter des variables métier calculées par l'émetteur
    (ex. ``nom_projet``/``date`` côté ``gestion_projet``). Best-effort total :
    toute erreur de formatage (accolade non fermée, etc.) renvoie le corps
    ORIGINAL sans lever — jamais de blocage d'une automatisation existante.
    """
    if not body or not context:
        return body
    try:
        return body.format_map(_SafeDict(**context))
    except Exception:  # pragma: no cover - défensif
        return body


def _message_body(rule, context):
    """Corps du message : texte littéral, sinon modèle Paramètres existant.

    Substitue les variables ``{var}`` (XPRJ23) depuis ``context`` quand le
    corps en contient — no-op quand aucune accolade n'est présente
    (comportement historique inchangé pour toutes les règles existantes).
    """
    cfg = rule.action_config or {}
    body = cfg.get('body')
    if body:
        return _substitute_variables(body, context)
    template_key = cfg.get('template')
    if template_key:
        try:
            from apps.parametres.models_messages import MessageTemplate
            corps = MessageTemplate.get_corps(
                rule.company, template_key, cfg.get('langue', 'fr'))
            return _substitute_variables(corps, context)
        except Exception:
            return ''
    return ''


def _send_whatsapp(rule, instance, company, context, user):
    # WhatsApp est un canal MANUEL (lien wa.me) — aucun envoi automatique
    # n'existe dans l'app. On prépare donc le lien et on journalise ; pas
    # d'effet réseau. Sans numéro exploitable → no-op.
    phone = _resolve_phone(instance)
    if not phone:
        return Status.NOOP, 'Aucun numéro WhatsApp : envoi ignoré.'
    body = _message_body(rule, context)
    try:
        from apps.ventes.utils.whatsapp import build_wa_url
        url = build_wa_url(phone, body or '')
    except Exception:
        url = None
    if not url:
        return Status.NOOP, 'Numéro WhatsApp inexploitable : envoi ignoré.'
    return Status.SUCCESS, f'Lien WhatsApp préparé pour {phone}.'


def _send_email(rule, instance, company, context, user):
    to = _resolve_email(instance)
    if not to:
        return Status.NOOP, 'Aucune adresse email : envoi ignoré.'
    # Sujet/corps : le modèle de message stocké (par société, canal email) sert
    # de source éditable. L'``action_config`` explicite garde la priorité ; à
    # défaut, on résout depuis ``ModeleMessage``, qui retombe lui-même sur
    # « Notification Taqinor » tant qu'aucun modèle n'est enregistré — donc le
    # comportement reste identique à l'ancien sujet codé en dur.
    tmpl_objet, tmpl_corps = ModeleMessage.resolve(
        company, CanalMessage.EMAIL)
    body = _message_body(rule, context) or tmpl_corps
    subject = (rule.action_config or {}).get('subject') or tmpl_objet \
        or 'Notification Taqinor'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or \
        getattr(settings, 'CONTACT_FROM_EMAIL', 'no-reply@taqinor.ma')
    try:
        from django.core.mail import send_mail
        # Honnête : on NE masque PAS l'échec (fail_silently=False) et on vérifie
        # le nombre de messages réellement remis. Un email perdu doit être
        # journalisé FAILED, jamais SUCCESS. En local le backend console remet
        # bien le message (compteur 1) : pas d'effet réseau, pas d'échec.
        sent = send_mail(
            subject, body or '', from_email, [to], fail_silently=False)
    except Exception as exc:
        return Status.FAILED, f'Email non envoyé : {exc}'
    if not sent:
        return Status.FAILED, f'Email non remis à {to}.'
    return Status.SUCCESS, f'Email envoyé à {to}.'


def _send_sms(rule, instance, company, context, user):
    # Aucun fournisseur SMS n'est configuré dans le repo : no-op sûr.
    phone = _resolve_phone(instance)
    if not phone:
        return Status.NOOP, 'Aucun numéro : SMS ignoré.'
    return Status.NOOP, 'Canal SMS non configuré : SMS ignoré.'


# ── Activité / tâche, assignation, champ, ticket SAV ───────────────────────

def _create_activity(rule, instance, company, context, user):
    """Crée une entrée chatter sur un lead (le seul chatter générique
    disponible). Pour les autres modèles → no-op journalisé."""
    body = (rule.action_config or {}).get('body') or rule.nom
    label = getattr(getattr(instance, '_meta', None), 'model_name', '')
    if label == 'lead':
        try:
            from apps.crm.models import LeadActivity
            LeadActivity.objects.create(
                company=company, lead=instance,
                kind=LeadActivity.Kind.NOTE, body=body, user=user)
            return Status.SUCCESS, 'Activité (note) créée sur le lead.'
        except Exception as exc:
            return Status.FAILED, f'Activité non créée : {exc}'
    return Status.NOOP, 'Aucun chatter pour ce modèle : activité ignorée.'


def _assign_record(rule, instance, company, context, user):
    """Assigne l'enregistrement à un utilisateur via son champ d'assignation
    naturel (owner / technicien_responsable). No-op si absent."""
    user_id = (rule.action_config or {}).get('user_id')
    if not user_id:
        return Status.NOOP, "Aucun utilisateur cible : assignation ignorée."
    field = None
    for cand in ('owner', 'technicien_responsable'):
        if _has_field(instance, cand):
            field = cand
            break
    if field is None:
        return Status.NOOP, "Modèle non assignable : assignation ignorée."
    try:
        from django.contrib.auth import get_user_model
        target = get_user_model().objects.filter(
            pk=user_id, company=company).first()
        if target is None:
            return Status.NOOP, 'Utilisateur cible inconnu : ignoré.'
        setattr(instance, f'{field}_id', target.pk)
        instance.save(update_fields=[f'{field}_id'])
        return Status.SUCCESS, f'Assigné à {target} via « {field} ».'
    except Exception as exc:
        return Status.FAILED, f'Assignation échouée : {exc}'


def _set_field(rule, instance, company, context, user):
    cfg = rule.action_config or {}
    field = cfg.get('field')
    if not field or not _has_field(instance, field):
        return Status.NOOP, f'Champ « {field} » absent : mise à jour ignorée.'
    # Sécurité : on n'autorise jamais d'écrire la société ni un prix d'achat.
    if field in ('company', 'company_id', 'prix_achat'):
        return Status.SKIPPED, f'Champ « {field} » protégé : refusé.'
    value = cfg.get('value')
    try:
        setattr(instance, field, value)
        instance.save(update_fields=[field])
        return Status.SUCCESS, f'Champ « {field} » mis à jour.'
    except Exception as exc:
        return Status.FAILED, f'Mise à jour échouée : {exc}'


def _create_sav_ticket(rule, instance, company, context, user):
    """Crée un ticket SAV pour le client de l'enregistrement déclencheur."""
    cfg = rule.action_config or {}
    client = _resolve_client(instance)
    if client is None:
        return Status.NOOP, 'Aucun client résolu : ticket SAV ignoré.'
    try:
        from apps.sav.models import Ticket
        from apps.ventes.utils.references import create_with_reference

        installation = instance if _model_name(instance) == 'installation' \
            else None

        def _save(ref):
            return Ticket.objects.create(
                company=company,
                reference=ref,
                client=client,
                installation=installation,
                type=cfg.get('type', Ticket.Type.PREVENTIF),
                priorite=cfg.get('priorite', Ticket.Priorite.NORMALE),
                description=cfg.get('description') or rule.nom,
                created_by=user,
            )

        ticket = create_with_reference(Ticket, 'SAV', company, _save)
        return Status.SUCCESS, f'Ticket SAV {ticket.reference} créé.'
    except Exception as exc:
        return Status.FAILED, f'Ticket SAV non créé : {exc}'


def _create_custom_record(rule, instance, company, context, user):
    """NTEXT26 — matérialise un ``CustomRecord`` (objet personnalisé) depuis
    une automatisation.

    ``action_config = {'object_code': 'suivi-qualite', 'data': {...}}`` — les
    valeurs TEXTE de ``data`` supportent la substitution ``{var}`` depuis
    ``context`` (même mécanisme que les corps de message, XPRJ23). La
    validation réutilise EXACTEMENT le chemin de l'API
    (``customfields.serializers.validate_custom_data`` — même règles
    obligatoire/type/``requis_si`` que la création manuelle), jamais de
    contournement. ``customfields`` est une app foundation (cf. CLAUDE.md),
    l'import direct de ses modèles/serializers est autorisé."""
    cfg = rule.action_config or {}
    object_code = (cfg.get('object_code') or '').strip()
    if not object_code:
        return Status.NOOP, 'Aucun objet personnalisé configuré : action ignorée.'
    from apps.customfields.models import CustomObjectDef, CustomRecord
    objet = CustomObjectDef.objects.filter(
        company=company, code=object_code, actif=True).first()
    if objet is None:
        return Status.NOOP, (
            f'Objet personnalisé « {object_code} » introuvable : '
            f'création ignorée.')
    raw_data = cfg.get('data') or {}
    if not isinstance(raw_data, dict):
        raw_data = {}
    resolved = {
        key: (_substitute_variables(val, context)
              if isinstance(val, str) else val)
        for key, val in raw_data.items()
    }
    try:
        from apps.customfields.serializers import validate_custom_data
        clean = validate_custom_data(objet.field_module, company, resolved)
    except Exception as exc:
        return Status.FAILED, f'Enregistrement non créé : {exc}'
    try:
        CustomRecord.objects.create(
            company=company, objet=objet, data=clean, created_by=user)
        return Status.SUCCESS, f'Enregistrement « {objet.libelle} » créé.'
    except Exception as exc:
        return Status.FAILED, f'Enregistrement non créé : {exc}'


def _wait(rule, instance, company, context, user):
    """NTEXT7 — ``WAIT`` hors séquence : rien à suspendre.

    Dans une SÉQUENCE, une étape ``WAIT`` est interceptée par le moteur
    (``engine._run_steps``), qui écrit l'échéance de reprise et ne passe jamais
    par ce handler. Une règle dont l'action UNIQUE est ``WAIT`` n'a en revanche
    aucune suite à reprendre : no-op explicite plutôt qu'« action inconnue ».
    """
    return Status.NOOP, ("Attente sans suite : une étape « Attendre » n'a "
                         "d'effet que dans une séquence.")


class _SubActionView:
    """NTEXT6 — vue « règle » d'UNE sous-action de boucle.

    Même patron que ``engine._StepView`` : substitue le couple
    ``action_type``/``action_config`` et délègue TOUT le reste (société, nom…)
    à la règle porteuse. Jamais persistée.
    """

    __slots__ = ('_rule', 'action_type', 'action_config')

    def __init__(self, rule, action_type, action_config):
        self._rule = rule
        self.action_type = action_type
        self.action_config = action_config

    def __getattr__(self, name):
        return getattr(self._rule, name)


def _for_each(rule, instance, company, context, user):
    """NTEXT6 — répète des SOUS-ACTIONS sur chaque élément d'une liste.

    ``action_config = {'source': '<clé whitelistée>', 'sous_actions': [
    {'action_type': 'create_custom_record', 'action_config': {...}}, ...]}``.

    La liste vient EXCLUSIVEMENT du registre fermé
    ``automation.list_sources`` (jamais un accès modèle arbitraire), et l'on
    n'itère JAMAIS plus de ``MAX_ITERATIONS`` éléments : une source plus longue
    est tronquée et la troncature est dite dans le message du run (anti-DoS).

    Chaque élément est fusionné dans le contexte des sous-actions (ses clés
    alimentent la substitution ``{var}``), avec ``element_index`` (1-based).
    Une sous-action en échec n'interrompt pas la boucle ; une sous-action
    ``FOR_EACH`` imbriquée est refusée (pas de boucle de boucles).
    """
    from .list_sources import MAX_ITERATIONS, resolve_list

    cfg = rule.action_config or {}
    sous_actions = cfg.get('sous_actions') or []
    if not isinstance(sous_actions, list) or not sous_actions:
        return Status.NOOP, 'Aucune sous-action configurée : boucle ignorée.'

    elements, tronquee, erreur = resolve_list(
        cfg.get('source'), instance, company, context)
    if erreur:
        return Status.SKIPPED, erreur
    if not elements:
        return Status.NOOP, 'Liste vide : aucune itération.'

    faits = 0
    echecs = 0
    for index, element in enumerate(elements, start=1):
        sous_contexte = dict(context or {})
        if isinstance(element, dict):
            sous_contexte.update(element)
        else:  # pragma: no cover - les sources normalisent déjà en dicts
            sous_contexte['valeur'] = element
        sous_contexte['element_index'] = index
        for spec in sous_actions:
            if not isinstance(spec, dict):
                continue
            action_type = (spec.get('action_type') or '').strip()
            if not action_type:
                continue
            if action_type == ActionType.FOR_EACH:
                echecs += 1
                continue  # pas de boucle imbriquée (garde anti-DoS)
            vue = _SubActionView(
                rule, action_type, spec.get('action_config') or {})
            statut, _message = run(vue, instance, company, sous_contexte, user)
            if statut == Status.FAILED:
                echecs += 1
            else:
                faits += 1

    message = (f'Boucle : {len(elements)} élément(s) × '
               f'{len(sous_actions)} sous-action(s) — {faits} exécutée(s)')
    if echecs:
        message += f', {echecs} en échec'
    if tronquee:
        message += (f' (liste tronquée à la borne de {MAX_ITERATIONS} '
                    f'itérations)')
    message += '.'
    return (Status.FAILED if faits == 0 and echecs else Status.SUCCESS), message


# ── Helpers ───────────────────────────────────────────────────────────────

def _model_name(instance):
    meta = getattr(instance, '_meta', None)
    return getattr(meta, 'model_name', '') if meta else ''


def _has_field(instance, name):
    meta = getattr(instance, '_meta', None)
    if meta is None:
        return False
    return name in {f.name for f in meta.concrete_fields}


def _resolve_client(instance):
    client = getattr(instance, 'client', None)
    if client is not None:
        return client
    # Un lead peut résoudre vers un client via le service CRM existant.
    if _model_name(instance) == 'lead':
        try:
            from apps.crm.services import resolve_client_for_lead
            return resolve_client_for_lead(instance)
        except Exception:
            return None
    return None


_HANDLERS = {
    ActionType.SEND_WHATSAPP: _send_whatsapp,
    ActionType.SEND_EMAIL: _send_email,
    ActionType.SEND_SMS: _send_sms,
    ActionType.CREATE_ACTIVITY: _create_activity,
    ActionType.ASSIGN_RECORD: _assign_record,
    ActionType.SET_FIELD: _set_field,
    ActionType.CREATE_SAV_TICKET: _create_sav_ticket,
    ActionType.CREATE_CUSTOM_RECORD: _create_custom_record,
    ActionType.FOR_EACH: _for_each,
    ActionType.WAIT: _wait,
}
