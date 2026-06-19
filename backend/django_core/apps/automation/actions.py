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

from .models import ActionType, AutomationRun

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


def _message_body(rule, context):
    """Corps du message : texte littéral, sinon modèle Paramètres existant."""
    cfg = rule.action_config or {}
    body = cfg.get('body')
    if body:
        return body
    template_key = cfg.get('template')
    if template_key:
        try:
            from apps.parametres.models_messages import MessageTemplate
            return MessageTemplate.get_corps(
                rule.company, template_key, cfg.get('langue', 'fr'))
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
    body = _message_body(rule, context)
    subject = (rule.action_config or {}).get('subject') or 'Notification Taqinor'
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or \
        getattr(settings, 'CONTACT_FROM_EMAIL', 'no-reply@taqinor.ma')
    try:
        from django.core.mail import send_mail
        # En local le backend est la console : aucun envoi réel, jamais
        # d'échec — c'est notre no-op « sûr quand non configuré ».
        send_mail(subject, body or '', from_email, [to], fail_silently=True)
    except Exception as exc:
        return Status.FAILED, f'Email non envoyé : {exc}'
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
}
