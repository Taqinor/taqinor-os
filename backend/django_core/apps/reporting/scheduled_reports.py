"""N79 — Envoi par email programmé des rapports sauvegardés (Celery Beat).

Une tâche unique (`reporting.email_saved_reports`) décide, à chaque exécution, des
rapports DUS : ceux dont `schedule` correspond à la cadence courante (quotidienne
le matin, hebdomadaire le lundi) et qui ont au moins un destinataire. Pour chacun,
elle rend le rapport ciblé en .xlsx (builder partagé `apps.records.xlsx`) et
l'envoie via le backend email configuré.

Principes (règles fondatrices) :
  - NO-OP sûr : sans email configuré (clé Brevo/SMTP), AUCUN envoi réseau — la
    tâche se contente de ne rien envoyer (comportement actuel préservé). On
    réutilise `apps.ventes.email_service.is_email_configured`.
  - MULTI-TENANT : chaque rapport est rendu DANS la portée de sa société (jamais
    de fuite inter-société) ; le rendu est borné par `company`.
  - DÉFENSIF/IDEMPOTENT : chaque rapport est traité isolément (try/except) ; une
    erreur n'arrête pas les suivants. Aucune donnée métier n'est mutée (seul
    `last_sent_at` du rapport envoyé est horodaté).
  - Aucun prix d'achat / marge n'est jamais exposé (rapports client-safe).
  Texte utilisateur en FRANÇAIS ; code/identifiants en anglais.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

CASABLANCA_TZ = 'Africa/Casablanca'


def _casablanca_now():
    from django.utils import timezone
    try:
        from zoneinfo import ZoneInfo
        return timezone.now().astimezone(ZoneInfo(CASABLANCA_TZ))
    except Exception:  # pragma: no cover - zoneinfo absent (très improbable)
        return timezone.localtime()


def _is_email_configured():
    """Réutilise l'helper de configuration email des ventes (Brevo/SMTP)."""
    try:
        from apps.ventes.email_service import is_email_configured
        return is_email_configured()
    except Exception:  # pragma: no cover - défensif
        return False


# ── Rendu d'un rapport → (en-têtes, lignes). Borné à la société. ─────────────

def _company_filter(company):
    return {'company': company} if company is not None else {}


def render_sales(report):
    """Funnel des leads par étape (miroir léger de reports.sales_report)."""
    from apps.crm import stages as stage_mod
    from apps.crm.models import Lead

    co = _company_filter(report.company)
    leads = Lead.objects.filter(is_archived=False, **co)
    rows = []
    for key in stage_mod.STAGES:
        rows.append([
            stage_mod.STAGE_LABELS.get(key, key),
            leads.filter(stage=key).count(),
        ])
    return ['Étape', 'Leads'], rows


def render_stock(report):
    """Produits + quantités en stock (jamais de prix d'achat)."""
    from apps.stock.models import Produit

    co = _company_filter(report.company)
    rows = []
    for p in Produit.objects.filter(**co).order_by('nom'):
        rows.append([
            getattr(p, 'nom', '') or '',
            getattr(p, 'sku', '') or '',
            getattr(p, 'quantite_stock', 0) or 0,
        ])
    return ['Produit', 'Référence', 'Quantité en stock'], rows


def render_service(report):
    """Tickets SAV par statut (vue service)."""
    from apps.sav.models import Ticket

    co = _company_filter(report.company)
    tickets = Ticket.objects.filter(**co)
    labels = dict(Ticket.Statut.choices)
    rows = []
    for value, _label in Ticket.Statut.choices:
        rows.append([
            labels.get(value, value),
            tickets.filter(statut=value).count(),
        ])
    return ['Statut', 'Tickets'], rows


_RENDERERS = {
    'sales': render_sales,
    'stock': render_stock,
    'service': render_service,
}


def render_report_xlsx(report):
    """Rend un SavedReport en octets .xlsx (builder partagé). None si échec."""
    renderer = _RENDERERS.get(report.target_kind)
    if renderer is None:
        return None, None
    try:
        headers, rows = renderer(report)
    except Exception:  # pragma: no cover - défensif (modèle/requête)
        logger.warning('email_saved_reports: rendu %r en échec (rapport %s)',
                       report.target_kind, report.pk, exc_info=True)
        return None, None
    try:
        from apps.records.xlsx import workbook_bytes
        title = report.get_target_kind_display()
        return workbook_bytes(headers, rows, sheet_title=title), title
    except Exception:  # pragma: no cover - dépend d'openpyxl
        logger.warning('email_saved_reports: sérialisation xlsx en échec '
                       '(rapport %s)', report.pk, exc_info=True)
        return None, None


def _send_report_email(report, content, title):
    """Envoie le .xlsx aux destinataires via le backend configuré.

    NO-OP (renvoie False) si l'email n'est pas configuré ou sans destinataire.
    Best-effort : toute exception est capturée, jamais propagée."""
    recipients = report.recipient_list()
    if not recipients or not _is_email_configured():
        return False
    try:
        from django.conf import settings
        from django.core.mail import EmailMessage, get_connection

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or 'noreply@erp.local'
        subject = f'Rapport : {report.name}'[:300]
        body = (f'Bonjour,\n\nVeuillez trouver ci-joint le rapport « {report.name} » '
                f'({title}).\n\nCordialement.')
        connection = get_connection(fail_silently=True)
        msg = EmailMessage(
            subject=subject, body=body, from_email=from_email,
            to=recipients, connection=connection)
        filename = f'{report.target_kind}.xlsx'
        msg.attach(
            filename, content,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        msg.send(fail_silently=True)
        return True
    except Exception:  # pragma: no cover - dépend du backend réel
        logger.warning('email_saved_reports: envoi en échec (rapport %s)',
                       report.pk, exc_info=True)
        return False


def _due_schedules(now):
    """Cadences dues à l'instant `now` (Casablanca).

    La tâche est planifiée chaque jour (06:00) et le lundi (06:00). Pour rester
    robuste quelle que soit l'horloge réelle d'invocation, on considère « daily »
    toujours dû, et « weekly » dû uniquement le lundi (weekday() == 0)."""
    due = {'daily'}
    if now.weekday() == 0:  # lundi
        due.add('weekly')
    return due


@shared_task(name='reporting.email_saved_reports')
def email_saved_reports():
    """Envoie par email les rapports sauvegardés dus. Renvoie le nb d'envois.

    Sélectionne les rapports dont `schedule` est dû et qui ont un destinataire,
    les rend en .xlsx et les envoie. NO-OP propre si l'email n'est pas configuré
    (aucun envoi). Idempotent : seul `last_sent_at` est horodaté sur envoi réussi."""
    from .models import SavedReport

    now = _casablanca_now()
    due = _due_schedules(now)
    sent = 0
    try:
        reports = list(SavedReport.objects.filter(schedule__in=due))
    except Exception:  # pragma: no cover - défensif
        logger.warning('email_saved_reports: chargement des rapports impossible',
                       exc_info=True)
        return 0

    for report in reports:
        try:
            if not report.recipient_list():
                continue
            content, title = render_report_xlsx(report)
            if content is None:
                continue
            if _send_report_email(report, content, title):
                report.last_sent_at = now
                report.save(update_fields=['last_sent_at'])
                sent += 1
        except Exception:  # pragma: no cover - défensif par rapport
            logger.warning('email_saved_reports: échec sur le rapport %s',
                           getattr(report, 'pk', None), exc_info=True)
            continue
    logger.info('email_saved_reports: %s rapport(s) envoyé(s) (cadences=%s)',
                sent, ','.join(sorted(due)))
    return sent
