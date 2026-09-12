"""
NTNRG26 — Attestation carbone PDF certifiable, par site ou consolidée client.

FG286/287/288 exposent déjà le CO₂ évité (JSON/portail) — il manquait une
ATTESTATION PDF signée/horodatée (distincte du certificat RE FG287
générique, propre à `apps.ventes`) au format « bilan carbone » : méthodologie
affichée (facteur réseau utilisé, période, kWh évités → tCO₂, référence de
calcul), téléchargeable/partageable PAR SITE ou CONSOLIDÉE multi-sites pour
un client multi-installations.

Réutilise le calcul CO₂ EXISTANT (``selectors.co2_for_installation`` /
``selectors.client_environmental_dashboard``, FG286/288) — aucun second
calcul. 100 % LECTURE. Sans relevé sur la période, le PDF affiche un message
propre (« aucune production mesurée ») plutôt que d'échouer.
"""
from __future__ import annotations

from html import escape

from django.utils import timezone

from core.pdf import render_pdf

from .selectors import client_environmental_dashboard, co2_for_installation

_PAGE_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a1a; }
h1 { font-size: 20px; margin: 0 0 2px; }
.subtitle { color: #555; font-size: 12px; margin-bottom: 14px; }
.section-h { font-weight: 700; font-size: 13px; margin: 16px 0 6px;
  border-bottom: 1px solid #ddd; padding-bottom: 3px; }
.cards { display: flex; gap: 10px; margin-bottom: 6px; }
.card { flex: 1; border: 1px solid #e3e3e3; border-radius: 8px; padding: 10px; }
.card .k { font-size: 10px; color: #777; text-transform: uppercase; }
.card .big { font-size: 18px; font-weight: 700; }
.methodo { background: #f6f6f6; border: 1px solid #e0e0e0; border-radius: 6px;
  padding: 10px 12px; font-size: 10.5px; color: #444; margin-top: 10px; }
.empty { color: #b3261e; font-size: 12px; margin-top: 10px; }
.footer { margin-top: 18px; color: #888; font-size: 10px; }
"""


def _methodologie(co2_kg_par_kwh, periode_label):
    return (
        f'Méthodologie : le CO₂ évité est calculé en multipliant la '
        f'production photovoltaïque mesurée (kWh) par le facteur '
        f'd\'émission du réseau électrique marocain retenu '
        f'({co2_kg_par_kwh} kg CO₂/kWh) sur la période {periode_label}. '
        f'Référence de calcul : kWh produits × facteur réseau = kg CO₂ '
        f'évités, converti en tonnes (÷ 1000). Aucune double-comptabilisation '
        f'inter-sites — chaque relevé de production n\'est compté qu\'une fois.'
    )


def build_carbon_report_data_site(installation, *, since=None, until=None,
                                  co2_kg_par_kwh=None, today=None):
    """Données de l'attestation carbone d'UN site (FG286, ``co2_for_installation``).

    ``since``/``until`` (dates, optionnelles) bornent la période ; sans borne,
    toute la production mesurée. 100 % lecture.
    """
    today = today or timezone.localdate()
    data = co2_for_installation(
        installation, since=since, until=until, co2_kg_par_kwh=co2_kg_par_kwh)
    facteur = data['co2_kg_par_kwh']
    periode_label = (
        f'{since.isoformat() if since else "origine"} → '
        f'{until.isoformat() if until else today.isoformat()}')
    return {
        'scope': 'site',
        'reference': getattr(installation, 'reference', None),
        'periode_label': periode_label,
        'since': since.isoformat() if since else None,
        'until': until.isoformat() if until else None,
        'production_kwh': data['production_kwh'],
        'co2_kg': data['co2_kg'],
        'co2_tonnes': data['co2_tonnes'],
        'co2_kg_par_kwh': facteur,
        'has_data': data['production_kwh'] > 0,
        'methodologie': _methodologie(facteur, periode_label),
        'date_edition': today.isoformat(),
    }


def build_carbon_report_data_client(company, client_id, *,
                                    tarif_mad_par_kwh=None,
                                    co2_kg_par_kwh=None, today=None):
    """Données de l'attestation carbone CONSOLIDÉE d'un client multi-sites
    (FG288, ``client_environmental_dashboard``). 100 % lecture."""
    today = today or timezone.localdate()
    data = client_environmental_dashboard(
        company, client_id, tarif_mad_par_kwh=tarif_mad_par_kwh,
        co2_kg_par_kwh=co2_kg_par_kwh)
    facteur = data['co2_kg_par_kwh']
    periode_label = f'cumul depuis origine → {today.isoformat()}'
    return {
        'scope': 'client',
        'client': data['client'],
        'systems_count': data['systems_count'],
        'periode_label': periode_label,
        'production_kwh': data['total_production_kwh'],
        'co2_kg': data['co2_kg'],
        'co2_tonnes': data['co2_tonnes'],
        'co2_kg_par_kwh': facteur,
        'has_data': data['total_production_kwh'] > 0,
        'methodologie': _methodologie(facteur, periode_label),
        'date_edition': today.isoformat(),
    }


def _build_html(data, *, entreprise_nom=''):
    def _v(x):
        return escape(str(x)) if x is not None else '—'

    titre = ('Attestation carbone — site' if data['scope'] == 'site'
             else 'Attestation carbone — consolidée client')
    sous_titre = (
        f'Système {_v(data.get("reference"))}' if data['scope'] == 'site'
        else f'{_v(data.get("systems_count"))} système(s) · client #{_v(data.get("client"))}')

    if not data['has_data']:
        corps_vide = (
            '<p class="empty">Aucune production mesurée sur la période — '
            'aucune attestation chiffrée ne peut être établie pour l\'instant.</p>')
        cards = ''
    else:
        corps_vide = ''
        cards = (
            '<div class="cards">'
            f'<div class="card"><div class="k">Production</div>'
            f'<div class="big">{_v(data["production_kwh"])} kWh</div></div>'
            f'<div class="card"><div class="k">CO₂ évité</div>'
            f'<div class="big">{_v(data["co2_kg"])} kg</div></div>'
            f'<div class="card"><div class="k">CO₂ évité (t)</div>'
            f'<div class="big">{_v(data["co2_tonnes"])} t</div></div>'
            '</div>'
        )

    body = (
        f'<h1>{escape(titre)}</h1>'
        f'<div class="subtitle">{sous_titre} · période {_v(data["periode_label"])} '
        f'· édité le {_v(data["date_edition"])}</div>'
        + cards
        + corps_vide
        + '<div class="section-h">Méthodologie</div>'
        + f'<div class="methodo">{escape(data["methodologie"])}</div>'
        + f'<div class="footer">Attestation carbone · {escape(str(entreprise_nom or ""))}</div>'
    )
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
        f'<title>{escape(titre)}</title>'
        f'<style>{_PAGE_CSS}</style></head><body>{body}</body></html>'
    )


def render_carbon_report_pdf_site(installation, *, since=None, until=None,
                                  co2_kg_par_kwh=None, today=None):
    """Octets PDF de l'attestation carbone d'UN site."""
    data = build_carbon_report_data_site(
        installation, since=since, until=until,
        co2_kg_par_kwh=co2_kg_par_kwh, today=today)
    company = getattr(installation, 'company', None)
    entreprise_nom = getattr(company, 'nom', '') or ''
    return render_pdf(html=_build_html(data, entreprise_nom=entreprise_nom))


def render_carbon_report_pdf_client(company, client_id, *,
                                    tarif_mad_par_kwh=None,
                                    co2_kg_par_kwh=None, today=None):
    """Octets PDF de l'attestation carbone CONSOLIDÉE d'un client."""
    data = build_carbon_report_data_client(
        company, client_id, tarif_mad_par_kwh=tarif_mad_par_kwh,
        co2_kg_par_kwh=co2_kg_par_kwh, today=today)
    entreprise_nom = getattr(company, 'nom', '') or ''
    return render_pdf(html=_build_html(data, entreprise_nom=entreprise_nom))
