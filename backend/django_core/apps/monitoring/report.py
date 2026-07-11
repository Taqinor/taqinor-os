"""
FG289 — Rapport O&M périodique automatisé par système (PDF + email).

Assemble pour UN système, sur une période (mensuelle/trimestrielle), les
indicateurs déjà calculés ailleurs dans le module :

  * production de la période (depuis `ProductionReading`) ;
  * PR / disponibilité / dégradation / soiling (analytics O&M, FG279) ;
  * alarmes : drapeaux de sous-performance ouverts (N52) ;
  * recommandations : reco de nettoyage (FG283) + recours fabricant (FG284,
    si une garantie de production est configurée).

`render_om_report_pdf` rend un PDF auto-suffisant via WeasyPrint (déjà une
dépendance, comme l'energy report) SANS importer un autre app domaine.
`email_om_report` l'envoie via le backend e-mail Django configuré (console en
local, SendGrid si la clé est posée — aucune nouvelle dépendance, aucun coût
par défaut). No-op sûr (renvoie False) s'il n'y a pas de destinataire.

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()``) est
déléguée au service partagé ``core.pdf.render_pdf`` ; le GABARIT HTML
ci-dessus reste STRICTEMENT identique, donc le rendu est inchangé à l'octet
près.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from html import escape

from django.utils import timezone

from core.pdf import render_pdf

from .analytics import om_metrics, soiling_assessment
from .models import ProductionReading, UnderperformanceFlag
from .services import warranty_curve_overlay

# Périodes supportées (en jours) pour le rapport périodique.
PERIODS = {'monthly': 30, 'quarterly': 91}

_PAGE_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a1a; }
h1 { font-size: 20px; margin: 0 0 2px; }
.subtitle { color: #555; font-size: 12px; margin-bottom: 14px; }
.section-h { font-weight: 700; font-size: 13px; margin: 16px 0 6px;
  border-bottom: 1px solid #ddd; padding-bottom: 3px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
td, th { padding: 5px 6px; border-bottom: 1px solid #eee; text-align: left; }
.cards { display: flex; gap: 10px; }
.card { flex: 1; border: 1px solid #e3e3e3; border-radius: 8px; padding: 10px; }
.card .k { font-size: 10px; color: #777; text-transform: uppercase; }
.card .big { font-size: 18px; font-weight: 700; }
.alarm { color: #b3261e; font-weight: 700; }
.ok { color: #1b7f3b; font-weight: 700; }
.reco { margin: 3px 0; }
.footer { margin-top: 18px; color: #888; font-size: 10px; }
"""


def build_om_report_data(installation, *, period='monthly', today=None):
    """Données du rapport O&M pour un système sur la période. 100 % lecture."""
    today = today or timezone.localdate()
    window = PERIODS.get(period, 30)
    since = today - timedelta(days=window)

    period_kwh = Decimal('0')
    for r in (ProductionReading.objects
              .filter(installation=installation, date__gte=since, date__lte=today)
              .values_list('energy_kwh', flat=True)):
        period_kwh += Decimal(str(r))

    metrics = om_metrics(installation, today=today)
    soiling = soiling_assessment(installation, today=today)
    curve = warranty_curve_overlay(installation, today=today)

    open_flags = UnderperformanceFlag.objects.filter(
        installation=installation, is_open=True).count()

    recommendations = []
    if soiling.get('recommend_cleaning'):
        recommendations.append('Nettoyage des panneaux recommandé.')
    if curve.get('has_warranty') and curve.get('manufacturer_recourse'):
        recommendations.append(
            'Dérive anormale vs courbe garantie : recours fabricant à étudier.')
    if open_flags:
        recommendations.append(
            'Sous-performance détectée : vérification technique requise.')
    if not recommendations:
        recommendations.append('Aucune action requise sur la période.')

    return {
        'installation': installation.id,
        'reference': getattr(installation, 'reference', None),
        'period': period,
        'period_days': window,
        'period_kwh': period_kwh.quantize(Decimal('0.01')),
        'pr_pct': metrics['pr_pct'],
        'availability_pct': metrics['availability_pct'],
        'degradation_pct_per_year': metrics['degradation_pct_per_year'],
        'soiling_suspected': metrics['soiling_suspected'],
        'open_alarms': open_flags,
        'recommendations': recommendations,
        'date_edition': today.isoformat(),
    }


def build_om_report_html(data, *, entreprise_nom=''):
    """HTML auto-suffisant du rapport O&M (pour WeasyPrint)."""
    def _v(x):
        return escape(str(x)) if x is not None else '—'

    period_label = {'monthly': 'mensuel', 'quarterly': 'trimestriel'}.get(
        data['period'], data['period'])

    cards = (
        '<div class="cards">'
        f'<div class="card"><div class="k">Production période</div>'
        f'<div class="big">{_v(data["period_kwh"])} kWh</div></div>'
        f'<div class="card"><div class="k">PR</div>'
        f'<div class="big">{_v(data["pr_pct"])} %</div></div>'
        f'<div class="card"><div class="k">Disponibilité</div>'
        f'<div class="big">{_v(data["availability_pct"])} %</div></div>'
        '</div>'
    )

    alarms_html = (
        f'<span class="alarm">{data["open_alarms"]} alarme(s) ouverte(s)</span>'
        if data['open_alarms']
        else '<span class="ok">Aucune alarme ouverte</span>')

    recos = ''.join(
        f'<div class="reco">• {escape(r)}</div>'
        for r in data['recommendations'])

    body = (
        f'<h1>Rapport O&amp;M {escape(period_label)}</h1>'
        f'<div class="subtitle">Système {_v(data["reference"])} · '
        f'période {data["period_days"]} jours · édité le '
        f'{_v(data["date_edition"])}</div>'
        + cards
        + '<div class="section-h">Indicateurs</div>'
        + '<table>'
        + f'<tr><td>Dégradation annualisée</td><td>{_v(data["degradation_pct_per_year"])} %/an</td></tr>'
        + f'<tr><td>Soiling suspecté</td><td>{"oui" if data["soiling_suspected"] else "non"}</td></tr>'
        + '</table>'
        + '<div class="section-h">Alarmes</div>'
        + f'<p>{alarms_html}</p>'
        + '<div class="section-h">Recommandations</div>'
        + recos
        + f'<div class="footer">Rapport O&amp;M automatisé · {escape(str(entreprise_nom or ""))}</div>'
    )
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
        f'<title>Rapport O&amp;M — {_v(data["reference"])}</title>'
        f'<style>{_PAGE_CSS}</style></head><body>{body}</body></html>'
    )


def render_om_report_pdf(installation, *, period='monthly', today=None):
    """Octets PDF du rapport O&M périodique d'un système (core.pdf, ARC12)."""
    data = build_om_report_data(installation, period=period, today=today)
    company = getattr(installation, 'company', None)
    entreprise_nom = getattr(company, 'nom', '') or ''
    html = build_om_report_html(data, entreprise_nom=entreprise_nom)
    return render_pdf(html=html)


def email_om_report(installation, *, period='monthly', recipient=None,
                    today=None):
    """Génère le rapport O&M et l'envoie par e-mail (PDF en pièce jointe).

    Destinataire = `recipient` sinon l'e-mail du client du système. No-op sûr
    (renvoie False) sans destinataire. Renvoie True si l'envoi a été tenté.

    ARC39 — cet envoi reste un ``EmailMessage`` direct (destinataire CLIENT,
    PDF en pièce jointe — ``notifications.services.notify()`` ne sait pas
    joindre de fichier et son destinataire est un utilisateur applicatif, pas
    un client) : EXCEPTION documentée, même famille que
    ``ventes/email_service.py``/``installations/rfq_service.py`` (emails
    CLIENTS, pas des notifications internes). En complément, on notifie EN
    INTERNE (best-effort, canal central) les responsables que le rapport
    vient d'être envoyé — c'était jusqu'ici invisible côté équipe.
    """
    from django.core.mail import EmailMessage

    if recipient is None:
        client = getattr(installation, 'client', None)
        recipient = getattr(client, 'email', None) if client else None
    if not recipient:
        return False

    period_label = {'monthly': 'mensuel', 'quarterly': 'trimestriel'}.get(
        period, period)
    pdf_bytes = render_om_report_pdf(installation, period=period, today=today)
    ref = getattr(installation, 'reference', installation.id)

    msg = EmailMessage(
        subject=f'Rapport O&M {period_label} — système {ref}',
        body=('Veuillez trouver ci-joint le rapport de supervision '
              f'{period_label} du système {ref}.'),
        to=[recipient])
    msg.attach(f'rapport-om-{ref}.pdf', pdf_bytes, 'application/pdf')
    msg.send(fail_silently=True)

    try:
        _notify_rapport_envoye(installation, period_label, ref, recipient)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
    return True


def _notify_rapport_envoye(installation, period_label, ref, recipient):
    """ARC39 — notification INTERNE (canal central) qu'un rapport O&M a été
    envoyé au client. Best-effort, jamais bloquant pour l'envoi e-mail
    lui-même (déjà tenté par l'appelant)."""
    from apps.notifications import services as notif_services

    company = getattr(installation, 'company', None)
    if company is None:
        return
    recipients = notif_services.resolve_recipients(
        company, 'monitoring_rapport')
    titre = f'Rapport O&M {period_label} envoyé — système {ref}'
    corps = f'Rapport O&M {period_label} du système {ref} envoyé à {recipient}.'
    notif_services.notify_many(
        recipients, 'monitoring_rapport', title=titre, body=corps,
        company=company)
