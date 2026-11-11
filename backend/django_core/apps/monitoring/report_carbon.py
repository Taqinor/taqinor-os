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


def _facteur_imprime(company, co2_kg_par_kwh):
    """AMON41 — « 630 gCO₂/kWh — source ONEE, 15/01/2026 » (facteur réglé par
    la société), la valeur explicite de l'appelant, ou None sans facteur."""
    if co2_kg_par_kwh is None:
        from apps.parametres.selectors import facteur_co2_reseau
        reglage = facteur_co2_reseau(company)
        if reglage is None:
            return None
        date = reglage['date']
        return (f'{reglage["g_kwh"].normalize():f} gCO₂/kWh — source '
                f'{reglage["source"]}'
                + (f', {date:%d/%m/%Y}' if date else ''))
    return f'{co2_kg_par_kwh} kg CO₂/kWh'


def _methodologie(facteur_imprime, periode_label):
    if facteur_imprime is None:
        return ('Facteur d\'émission du réseau non réglé (Paramètres) : aucun '
                f'tonnage de CO₂ n\'est établi pour la période {periode_label}.')
    return (
        f'Méthodologie : le CO₂ évité est calculé en multipliant la '
        f'production photovoltaïque mesurée (kWh) par le facteur '
        f'd\'émission du réseau électrique marocain retenu '
        f'({facteur_imprime}) sur la période {periode_label}. '
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
        'methodologie': _methodologie(
            _facteur_imprime(installation.company, co2_kg_par_kwh),
            periode_label),
        'date_edition': today.isoformat(),
    }


def build_carbon_report_data_client(company, client_id, *,
                                    tarif_mad_par_kwh=None,
                                    co2_kg_par_kwh=None, today=None,
                                    since=None, until=None):
    """Données de l'attestation carbone CONSOLIDÉE d'un client multi-sites
    (FG288, ``client_environmental_dashboard``). 100 % lecture."""
    today = today or timezone.localdate()
    data = client_environmental_dashboard(
        company, client_id, tarif_mad_par_kwh=tarif_mad_par_kwh,
        co2_kg_par_kwh=co2_kg_par_kwh, since=since, until=until)
    facteur = data['co2_kg_par_kwh']
    if since is None and until is None:
        periode_label = f'cumul depuis origine → {today.isoformat()}'
    else:
        periode_label = (
            f'{since.isoformat() if since else "origine"} → '
            f'{until.isoformat() if until else today.isoformat()}')
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
        'methodologie': _methodologie(
            _facteur_imprime(company, co2_kg_par_kwh), periode_label),
        'date_edition': today.isoformat(),
    }


def _build_html(data, *, entreprise_nom=''):
    def _v(x):
        return escape(str(x)) if x is not None else '—'

    titre = ('Attestation carbone — site' if data['scope'] == 'site'
             else 'Attestation carbone — consolidée client')
    if data.get('certificat'):  # AMON94 — certificat du registre
        titre = f'Certificat carbone {data["certificat"]}'
    sous_titre = (
        f'Système {_v(data.get("reference"))}' if data['scope'] == 'site'
        else f'{_v(data.get("systems_count"))} système(s) · client #{_v(data.get("client"))}')
    if data.get('mention'):  # AMON111 — certificat annulé
        sous_titre = f'{escape(data["mention"])} · {sous_titre}'

    if not data['has_data']:
        corps_vide = (
            '<p class="empty">Aucune production mesurée sur la période — '
            'aucune attestation chiffrée ne peut être établie pour l\'instant.</p>')
        cards = ''
    else:
        corps_vide = ''
        # AMON41 — sans facteur réglé, aucune tonne imprimée.
        cartes_co2 = '' if data['co2_kg'] is None else (
            f'<div class="card"><div class="k">CO₂ évité</div>'
            f'<div class="big">{_v(data["co2_kg"])} kg</div></div>'
            f'<div class="card"><div class="k">CO₂ évité (t)</div>'
            f'<div class="big">{_v(data["co2_tonnes"])} t</div></div>')
        cards = (
            '<div class="cards">'
            f'<div class="card"><div class="k">Production</div>'
            f'<div class="big">{_v(data["production_kwh"])} kWh</div></div>'
            + cartes_co2 + '</div>'
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
                                    co2_kg_par_kwh=None, today=None,
                                    since=None, until=None):
    """Octets PDF de l'attestation carbone CONSOLIDÉE d'un client."""
    data = build_carbon_report_data_client(
        company, client_id, tarif_mad_par_kwh=tarif_mad_par_kwh,
        co2_kg_par_kwh=co2_kg_par_kwh, today=today, since=since,
        until=until)
    entreprise_nom = getattr(company, 'nom', '') or ''
    return render_pdf(html=_build_html(data, entreprise_nom=entreprise_nom))


# ── AMON94 — le certificat du registre comme document ────────────────────

SOURCE_GED_CERTIFICAT = 'monitoring.certificat_carbone'


def render_certificat_pdf(certificat):
    """AMON94 — PDF d'un certificat ÉMIS : sa référence, sa période et ses
    tonnes FIGÉES (jamais recalculées), le facteur réglé avec source et date.
    Réutilise ``_build_html`` (même gabarit que l'attestation)."""
    from decimal import Decimal

    from apps.installations import selectors as installations_selectors

    company = certificat.company
    periode_label = (f'{certificat.periode_debut.isoformat()} → '
                     f'{certificat.periode_fin.isoformat()}')
    tonnes = Decimal(str(certificat.tco2_evitees))
    installation = (installations_selectors.installation_scoped(
        company, certificat.installation_id)
        if certificat.installation_id else None)
    data = {
        'scope': 'site' if certificat.installation_id else 'client',
        'certificat': certificat.reference,
        'reference': getattr(installation, 'reference', None),
        'client': certificat.client_id, 'systems_count': None,
        'periode_label': periode_label, 'production_kwh': None,
        'co2_kg': (tonnes * 1000).quantize(Decimal('0.01')),
        'co2_tonnes': tonnes, 'has_data': True,
        'methodologie': _methodologie(
            _facteur_imprime(company, None), periode_label),
        'date_edition': timezone.localdate().isoformat(),
    }
    if certificat.statut == certificat.Statut.ANNULE:  # AMON111
        le = f' le {timezone.localtime(certificat.annule_le):%d/%m/%Y}' if certificat.annule_le else ''
        data['mention'] = f'ANNULÉ{le} — {certificat.motif_annulation}'
    entreprise_nom = getattr(company, 'nom', '') or ''
    return render_pdf(html=_build_html(data, entreprise_nom=entreprise_nom))


def deposer_certificat_ged(certificat, pdf):
    """AMON94 — dépose le PDF du certificat en GED et pose ``fichier_key``
    (clé de la version en vigueur). Best-effort journalisé : l'émission reste
    acquise même si le stockage est indisponible. Renvoie la clé ou ''."""
    import logging
    try:
        from apps.ged.services import deposit_document
        document, _created = deposit_document(
            company=certificat.company, nom=f'Certificat {certificat.reference}',
            source_type=SOURCE_GED_CERTIFICAT, source_id=certificat.pk,
            contenu_bytes=pdf, filename=f'{certificat.reference}.pdf',
            mime='application/pdf', cabinet_nom='Supervision',
            folder_nom='Certificats carbone', versionner_si_modifie=True)
        version = document.versions.order_by('-version').first()
        cle = getattr(version, 'file_key', '') or ''
        if cle:
            type(certificat).objects.filter(pk=certificat.pk).update(
                fichier_key=cle)
            certificat.fichier_key = cle
        return cle
    except Exception:
        logging.getLogger(__name__).warning(
            'AMON94 : dépôt GED du certificat %s ignoré', certificat.reference,
            exc_info=True)
        return ''


def pdf_certificat(certificat):
    """AMON94 — octets du PDF du certificat : la version GED en vigueur, ou
    (absente) un rendu re-déposé ; annulé : rendu avec la mention, sans dépôt."""
    if certificat.statut == certificat.Statut.ANNULE:  # AMON111 — jamais la version GED d'émission
        return render_certificat_pdf(certificat)
    from apps.ged import services as ged_services
    document = ged_services.find_document_by_source(
        certificat.company, source_type=SOURCE_GED_CERTIFICAT,
        source_id=certificat.pk)
    version = (document.versions.order_by('-version').first()
               if document is not None else None)
    if version is not None and version.file_key:
        # ASEC58 — lecture gardée (clé hors société refusée).
        data, err = ged_services._fetch_version_bytes(version)
        if data and not err:
            return data
    pdf = render_certificat_pdf(certificat)
    deposer_certificat_ged(certificat, pdf)
    return pdf


def tco2_evitees_periode(company, *, installation=None, client_id=None,
                         since, until):
    """ASAV102 — tCO₂ évitées MESURÉES d'une cible sur une période, pour
    l'émission d'un certificat du registre (NTNRG27). Même calcul que
    l'attestation PDF ci-dessus (aucun second calcul, aucune saisie) : un
    système (``installation``) OU un client consolidé (``client_id``).

    Renvoie ``(tonnes: Decimal à 0,001, has_data: bool)``."""
    from decimal import Decimal

    if installation is not None:
        data = build_carbon_report_data_site(
            installation, since=since, until=until)
    else:
        data = build_carbon_report_data_client(
            company, client_id, since=since, until=until)
    if data['co2_tonnes'] is None:  # AMON41 — aucun facteur réglé
        return None, bool(data['has_data'])
    tonnes = Decimal(str(data['co2_tonnes'])).quantize(Decimal('0.001'))
    return tonnes, bool(data['has_data'])
