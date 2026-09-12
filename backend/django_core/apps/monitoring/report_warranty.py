"""
NTNRG11 — Rapport CONTRACTUEL mensuel de garantie de performance (PDF).

FG282/FG289 calculent déjà l'écart production réelle vs garantie
(``services.production_warranty_status``) et le rapport O&M générique
(``report.py``) — il manquait un PDF CONTRACTUEL dédié, à la mise en page
distincte de l'O&M : mention légale de la clause de garantie + tableau
MENSUEL de l'écart et de la pénalité CUMULÉE sur l'année contractuelle en
cours (ou une année passée close via ``?annee=``).

AUD508 — comme ``production_warranty_status``, le garanti comparé à
n'importe quel mois de l'année EN COURS est PRORATÉ au jour écoulé (jamais
un objectif annuel complet comparé à un réel forcément partiel) : le
tableau mensuel prote la MÊME logique de proration, appliquée à la fin de
CHAQUE mois plutôt qu'à aujourd'hui seul.

100 % LECTURE. ``render_warranty_report_pdf`` réutilise ``core.pdf.render_pdf``
(WeasyPrint, déjà une dépendance — comme le rapport O&M) SANS importer un
autre app domaine.
"""
from __future__ import annotations

import calendar
from datetime import date as _date
from decimal import Decimal
from html import escape

from django.utils import timezone

from core.pdf import render_pdf

from .models import ProductionReading, ProductionWarranty

# Libellés de mois en FRANÇAIS (jamais `calendar.month_name`, en anglais).
_MOIS_FR = [
    '', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

_PAGE_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a1a; }
h1 { font-size: 20px; margin: 0 0 2px; }
.subtitle { color: #555; font-size: 12px; margin-bottom: 10px; }
.legal { background: #f6f6f6; border: 1px solid #e0e0e0; border-radius: 6px;
  padding: 10px 12px; font-size: 10.5px; color: #444; margin-bottom: 14px; }
.section-h { font-weight: 700; font-size: 13px; margin: 16px 0 6px;
  border-bottom: 1px solid #ddd; padding-bottom: 3px; }
table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
td, th { padding: 5px 6px; border-bottom: 1px solid #eee; text-align: right; }
th { text-align: right; color: #555; }
td:first-child, th:first-child { text-align: left; }
.cards { display: flex; gap: 10px; margin-bottom: 6px; }
.card { flex: 1; border: 1px solid #e3e3e3; border-radius: 8px; padding: 10px; }
.card .k { font-size: 10px; color: #777; text-transform: uppercase; }
.card .big { font-size: 18px; font-weight: 700; }
.alarm { color: #b3261e; font-weight: 700; }
.ok { color: #1b7f3b; font-weight: 700; }
.footer { margin-top: 18px; color: #888; font-size: 10px; }
"""

_MENTION_LEGALE = (
    "Ce document est établi en application de la clause contractuelle de "
    "garantie de production souscrite pour ce système. Le productible "
    "garanti est dégradé annuellement selon le taux contractuel et comparé "
    "à la production réellement mesurée. Une franchise contractuelle "
    "(tolérance) s'applique avant tout calcul de compensation. Les montants "
    "affichés pour l'année en cours sont PROVISOIRES (prorata temporis) et "
    "ne deviennent définitifs qu'à la clôture de l'exercice."
)


def _q(value, places='0.01'):
    return Decimal(str(value)).quantize(Decimal(places)) if value is not None else None


def _fin_mois(year, month, today):
    """Dernier jour COUVERT par le mois ``month`` : le 30/31 s'il est déjà
    passé, sinon ``today`` si ``month`` est le mois en cours."""
    dernier_jour_calendaire = _date(
        year, month, calendar.monthrange(year, month)[1])
    if year == today.year and month == today.month:
        return min(today, dernier_jour_calendaire)
    return dernier_jour_calendaire


def build_warranty_report_data(installation, *, year=None, today=None):
    """Données du rapport contractuel de garantie pour un système/année.

    Renvoie ``{'has_warranty': False}`` (no-op gracieux) si aucune garantie
    de production n'est configurée pour ce système — l'appelant (vue) en
    déduit un 404 propre plutôt qu'un rapport vide.
    """
    today = today or timezone.localdate()
    year = int(year or today.year)

    warranty = getattr(installation, 'production_warranty', None)
    if warranty is None:
        warranty = (ProductionWarranty.objects
                    .filter(installation=installation).first())
    if warranty is None:
        return {'has_warranty': False}

    days_in_year = (_date(year, 12, 31) - _date(year, 1, 1)).days + 1
    guaranteed_full = warranty.guaranteed_kwh_for_year(year)
    tolerance_rate = Decimal(str(warranty.tolerance_pct)) / Decimal('100')
    tarif = Decimal(str(warranty.compensation_mad_per_kwh))

    last_month = today.month if year == today.year else 12
    year_in_progress = year == today.year

    monthly = []
    cumulative_actual = Decimal('0')
    for month in range(1, last_month + 1):
        debut_mois = _date(year, month, 1)
        fin_mois = _fin_mois(year, month, today)

        month_kwh = Decimal('0')
        for energie in (ProductionReading.objects
                        .filter(installation=installation,
                                date__gte=debut_mois, date__lte=fin_mois)
                        .values_list('energy_kwh', flat=True)):
            month_kwh += Decimal(str(energie))
        cumulative_actual += month_kwh

        jours_ecoules = (fin_mois - _date(year, 1, 1)).days + 1
        guaranteed_cum = guaranteed_full * (
            Decimal(jours_ecoules) / Decimal(days_in_year))

        shortfall_cum = guaranteed_cum - cumulative_actual
        if shortfall_cum < 0:
            shortfall_cum = Decimal('0')
        tolerance_kwh = guaranteed_cum * tolerance_rate
        compensable_cum = shortfall_cum - tolerance_kwh
        if compensable_cum < 0:
            compensable_cum = Decimal('0')
        penalty_cum = compensable_cum * tarif

        monthly.append({
            'month': month,
            'month_label': _MOIS_FR[month],
            'production_kwh': _q(month_kwh),
            'guaranteed_cumule_kwh': _q(guaranteed_cum),
            'actual_cumule_kwh': _q(cumulative_actual),
            'ecart_cumule_kwh': _q(shortfall_cum),
            'penalite_cumulee_mad': _q(penalty_cum),
        })

    final = monthly[-1] if monthly else None
    return {
        'has_warranty': True,
        'installation': installation.id,
        'reference': getattr(installation, 'reference', None),
        'year': year,
        'year_in_progress': year_in_progress,
        'tolerance_pct': warranty.tolerance_pct,
        'compensation_mad_per_kwh': warranty.compensation_mad_per_kwh,
        'guaranteed_year_kwh': _q(guaranteed_full),
        'monthly': monthly,
        'total_actual_kwh': final['actual_cumule_kwh'] if final else _q(Decimal('0')),
        'total_ecart_kwh': final['ecart_cumule_kwh'] if final else _q(Decimal('0')),
        'total_penalite_mad': final['penalite_cumulee_mad'] if final else _q(Decimal('0')),
        'date_edition': today.isoformat(),
    }


def build_warranty_report_html(data, *, entreprise_nom=''):
    """HTML auto-suffisant du rapport contractuel de garantie (WeasyPrint)."""
    def _v(x):
        return escape(str(x)) if x is not None else '—'

    cards = (
        '<div class="cards">'
        f'<div class="card"><div class="k">Production cumulée</div>'
        f'<div class="big">{_v(data["total_actual_kwh"])} kWh</div></div>'
        f'<div class="card"><div class="k">Écart cumulé</div>'
        f'<div class="big">{_v(data["total_ecart_kwh"])} kWh</div></div>'
        f'<div class="card"><div class="k">Pénalité cumulée</div>'
        f'<div class="big">{_v(data["total_penalite_mad"])} MAD</div></div>'
        '</div>'
    )

    rows = ''.join(
        '<tr>'
        f'<td>{_v(m["month_label"])}</td>'
        f'<td>{_v(m["production_kwh"])}</td>'
        f'<td>{_v(m["guaranteed_cumule_kwh"])}</td>'
        f'<td>{_v(m["actual_cumule_kwh"])}</td>'
        f'<td>{_v(m["ecart_cumule_kwh"])}</td>'
        f'<td>{_v(m["penalite_cumulee_mad"])}</td>'
        '</tr>'
        for m in data['monthly']
    )

    provisoire = (
        '<p class="alarm">Montants PROVISOIRES — année en cours.</p>'
        if data['year_in_progress']
        else '<p class="ok">Année clôturée — montants définitifs.</p>')

    body = (
        f'<h1>Rapport de garantie de performance {data["year"]}</h1>'
        f'<div class="subtitle">Système {_v(data["reference"])} · '
        f'garanti {_v(data["guaranteed_year_kwh"])} kWh/an · tolérance '
        f'{_v(data["tolerance_pct"])} % · édité le {_v(data["date_edition"])}</div>'
        f'<div class="legal">{escape(_MENTION_LEGALE)}</div>'
        + cards
        + provisoire
        + '<div class="section-h">Écart et pénalité cumulée par mois</div>'
        + '<table><thead><tr>'
        + '<th>Mois</th><th>Prod. mois (kWh)</th><th>Garanti cumulé (kWh)</th>'
          '<th>Réel cumulé (kWh)</th><th>Écart cumulé (kWh)</th>'
          '<th>Pénalité cumulée (MAD)</th>'
        + '</tr></thead><tbody>'
        + rows
        + '</tbody></table>'
        + f'<div class="footer">Rapport contractuel de garantie · {escape(str(entreprise_nom or ""))}</div>'
    )
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
        f'<title>Rapport de garantie — {_v(data["reference"])}</title>'
        f'<style>{_PAGE_CSS}</style></head><body>{body}</body></html>'
    )


def render_warranty_report_pdf(installation, *, year=None, today=None):
    """Octets PDF du rapport contractuel de garantie d'un système/année."""
    data = build_warranty_report_data(installation, year=year, today=today)
    company = getattr(installation, 'company', None)
    entreprise_nom = getattr(company, 'nom', '') or ''
    html = build_warranty_report_html(data, entreprise_nom=entreprise_nom)
    return render_pdf(html=html)
