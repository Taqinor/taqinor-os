# -*- coding: utf-8 -*-
"""Rapport de production énergétique ESTIMÉE (PDF client-facing, FR).

Ce rapport est une ESTIMATION : il n'y a AUCune donnée de monitoring mesurée.
La production est dérivée de la puissance nominale du système (kWc) et d'un
rendement spécifique (kWh/kWc/an, hypothèse marocaine par défaut), ou d'une
saisie manuelle de la production annuelle. Les économies et le CO₂ évité en
découlent via un tarif électricité (MAD/kWh) et un facteur réseau (kg CO₂/kWh).

Toutes les hypothèses sont des valeurs par défaut SURCHARGEABLES ; rien n'est
mesuré et chaque hypothèse est libellée « estimation » dans le PDF.

CÔTÉ CLIENT : AUCUN prix d'achat, AUCUNE marge — jamais. Le rapport ne lit que
la puissance nominale et l'identité du système ; aucun prix interne n'est lu.

Rendu via WeasyPrint (octets PDF en mémoire), comme apps.ventes.utils.pdf —
le moteur premium du devis n'est jamais importé ni modifié.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from html import escape

# ── Hypothèses PAR DÉFAUT (toutes surchargeables, toutes « estimations ») ─────
# Rendement spécifique marocain typique (irradiation + pertes système) : on
# retient une valeur centrale prudente dans la fourchette 1500–1700.
DEFAULT_RENDEMENT_KWH_PAR_KWC_AN = Decimal('1600')
# Tarif électricité moyen indicatif (MAD/kWh TTC) — surchargeable par client.
DEFAULT_TARIF_MAD_PAR_KWH = Decimal('1.40')
# Facteur d'émission du réseau marocain (kg CO₂ évité par kWh autoproduit).
DEFAULT_CO2_KG_PAR_KWH = Decimal('0.81')
# Période par défaut si rien n'est fourni : 12 mois.
DEFAULT_NB_MOIS = 12


def _to_decimal(value, default=None):
    """Convertit en Decimal en tolérant str/float/int/None. None ou vide ⇒
    `default`. Une valeur invalide ⇒ `default` (jamais d'exception)."""
    if value is None or value == '':
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _months_between(start, end):
    """Nombre de mois (≥ 0, Decimal) couverts par [start, end] inclus, calculé
    au jour près (≈ 30,44 jours/mois)."""
    if start is None or end is None or end < start:
        return None
    jours = Decimal((end - start).days + 1)
    return (jours / Decimal('30.4375'))


def compute_energy_estimate(
    puissance_kwc,
    *,
    nb_mois=None,
    date_debut=None,
    date_fin=None,
    production_annuelle_kwh=None,
    rendement_kwh_par_kwc_an=None,
    tarif_mad_par_kwh=None,
    co2_kg_par_kwh=None,
):
    """Calcule l'estimation de production / économies / CO₂ évité sur la période.

    Entrées (tout surchargeable, tout optionnel sauf un dénominateur de période) :
      - `puissance_kwc` : puissance nominale du système (kWc) — base du calcul
        quand aucune production annuelle manuelle n'est donnée.
      - `production_annuelle_kwh` : surcharge MANUELLE de la production annuelle
        de référence ; si fournie, elle prime sur le calcul kWc × rendement.
      - période : `nb_mois` (nombre de mois) OU [`date_debut`, `date_fin`].
      - hypothèses : `rendement_kwh_par_kwc_an`, `tarif_mad_par_kwh`,
        `co2_kg_par_kwh` (valeurs par défaut marocaines sinon).

    Renvoie un dict de nombres « sains » (Decimal arrondis) + les hypothèses
    effectivement retenues, pour un rendu identique à l'écran et au PDF.
    """
    kwc = _to_decimal(puissance_kwc, Decimal('0')) or Decimal('0')
    rendement = (_to_decimal(rendement_kwh_par_kwc_an)
                 or DEFAULT_RENDEMENT_KWH_PAR_KWC_AN)
    tarif = _to_decimal(tarif_mad_par_kwh) or DEFAULT_TARIF_MAD_PAR_KWH
    co2 = _to_decimal(co2_kg_par_kwh)
    if co2 is None:
        co2 = DEFAULT_CO2_KG_PAR_KWH

    # Production ANNUELLE de référence : saisie manuelle si fournie, sinon
    # kWc × rendement spécifique.
    prod_manuelle = _to_decimal(production_annuelle_kwh)
    manuelle = prod_manuelle is not None and prod_manuelle > 0
    if manuelle:
        prod_annuelle = prod_manuelle
    else:
        prod_annuelle = kwc * rendement

    # Période en mois : priorité aux dates si valides, sinon nb_mois, sinon 12.
    mois = None
    debut = date_debut if isinstance(date_debut, date) else None
    fin = date_fin if isinstance(date_fin, date) else None
    if debut is not None and fin is not None:
        mois = _months_between(debut, fin)
    if mois is None:
        mois = _to_decimal(nb_mois)
    if mois is None or mois <= 0:
        mois = Decimal(DEFAULT_NB_MOIS)

    fraction_annee = mois / Decimal('12')
    production_kwh = prod_annuelle * fraction_annee
    economies_mad = production_kwh * tarif
    co2_kg = production_kwh * co2
    co2_tonnes = co2_kg / Decimal('1000')

    q0 = Decimal('1')
    q2 = Decimal('0.01')
    q3 = Decimal('0.001')
    return {
        'puissance_kwc': kwc,
        'production_annuelle_kwh': prod_annuelle.quantize(q0),
        'nb_mois': mois.quantize(q2),
        'production_kwh': production_kwh.quantize(q0),
        'economies_mad': economies_mad.quantize(q2),
        'co2_kg': co2_kg.quantize(q0),
        'co2_tonnes': co2_tonnes.quantize(q3),
        # Hypothèses effectivement retenues (libellées « estimation » au rendu).
        'rendement_kwh_par_kwc_an': rendement.quantize(q0),
        'tarif_mad_par_kwh': tarif.quantize(q2),
        'co2_kg_par_kwh': co2.quantize(q3),
        'production_manuelle': manuelle,
    }


# ── Rendu PDF (WeasyPrint, HTML auto-suffisant — pas de moteur premium) ───────
def _fr_date(value):
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    return str(value)[:10]


def _fr_num(value, decimals=0):
    """Nombre au format FR (espace fine comme séparateur de milliers, virgule
    décimale). Accepte Decimal/float/int/None."""
    if value is None:
        return '—'
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    q = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
    d = d.quantize(q)
    neg = d < 0
    d = abs(d)
    entier, _, frac = f'{d:.{decimals}f}'.partition('.')
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    s = ' '.join(groupes)
    if decimals and frac:
        s = f'{s},{frac}'
    return f'-{s}' if neg else s


_PAGE_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Helvetica Neue',Arial,sans-serif;font-size:10.5pt;
  color:#1f2937;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
@page{size:A4;margin:16mm 14mm;}
.hdr{display:flex;align-items:center;justify-content:space-between;
  border-bottom:3px solid #0f766e;padding-bottom:12px;margin-bottom:18px;}
.hdr-logo img{height:46px;width:auto;object-fit:contain;display:block;}
.hdr-brand{font-size:16pt;font-weight:800;color:#0f766e;letter-spacing:.5px;}
.hdr-meta{text-align:right;font-size:8pt;color:#6b7280;line-height:1.5;}
.doc-kind{color:#0f766e;font-weight:800;font-size:12pt;letter-spacing:.4px;}
h1{font-size:18pt;color:#0f172a;margin:4px 0 4px;}
.subtitle{font-size:9.5pt;color:#6b7280;margin-bottom:18px;}
.party{display:flex;justify-content:space-between;gap:24px;margin-bottom:18px;}
.party .blk{font-size:9pt;line-height:1.55;color:#374151;}
.party .lbl{font-size:6.5pt;font-weight:700;letter-spacing:.6px;
  text-transform:uppercase;color:#9ca3af;margin-bottom:3px;}
.party strong{color:#0f172a;font-size:10pt;}
.section-h{font-size:8pt;font-weight:800;letter-spacing:.7px;text-transform:uppercase;
  color:#0f766e;margin:18px 0 8px;border-bottom:1px solid #e5e7eb;padding-bottom:4px;}
table{width:100%;border-collapse:collapse;font-size:9.5pt;}
table th{background:#f1f5f9;color:#475569;font-size:6.8pt;font-weight:700;
  text-transform:uppercase;letter-spacing:.5px;padding:7px 9px;text-align:left;
  border-bottom:1px solid #e2e8f0;}
table td{padding:6px 9px;border-bottom:1px solid #eef2f7;color:#374151;}
table td.v{text-align:right;font-weight:700;color:#0f172a;}
.cards{display:flex;gap:12px;margin:6px 0 4px;}
.card{flex:1;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;
  background:#f8fafc;}
.card .k{font-size:7pt;font-weight:700;letter-spacing:.5px;text-transform:uppercase;
  color:#0f766e;margin-bottom:6px;}
.card .big{font-size:17pt;font-weight:800;color:#0f172a;line-height:1.1;}
.card .u{font-size:8pt;color:#6b7280;margin-top:2px;}
.note{font-size:8pt;color:#6b7280;line-height:1.5;margin-top:6px;}
.estim{display:inline-block;background:#fef3c7;border:1px solid #f59e0b;
  border-radius:5px;padding:3px 9px;font-size:7.5pt;font-weight:700;
  color:#92400e;margin-bottom:12px;}
.ftr{margin-top:26px;border-top:1px solid #e5e7eb;padding-top:8px;
  font-size:7pt;color:#9ca3af;text-align:center;line-height:1.5;}
"""


def _logo_html(ctx):
    uri = ctx.get('logo_uri')
    if uri:
        return (f'<div class="hdr-logo"><img src="{escape(uri, quote=True)}" '
                f'alt="logo"></div>')
    nom = escape(str(ctx.get('entreprise_nom') or 'TAQINOR'))
    return f'<div class="hdr-brand">{nom}</div>'


def build_energy_report_html(ctx, system, client, est, period):
    """HTML auto-suffisant du rapport de production estimée (une page)."""
    today = _fr_date(date.today())

    # En-tête société.
    meta_lines = []
    if ctx.get('entreprise_adresse'):
        meta_lines.append(escape(str(ctx['entreprise_adresse']).replace('\n', ' ')))
    contact = []
    if ctx.get('entreprise_telephone'):
        contact.append(escape(str(ctx['entreprise_telephone'])))
    if ctx.get('entreprise_email'):
        contact.append(escape(str(ctx['entreprise_email'])))
    if contact:
        meta_lines.append(' · '.join(contact))
    meta_html = '<br>'.join(meta_lines)

    header = (
        f'<div class="hdr">{_logo_html(ctx)}'
        f'<div class="hdr-meta"><div class="doc-kind">Rapport de production</div>'
        f'{meta_html}</div></div>'
    )

    # Émetteur / destinataire.
    cl_nom = escape(f"{client.get('nom', '')} "
                    f"{client.get('prenom', '') or ''}".strip()) or '—'
    cl_lines = []
    for key in ('adresse', 'telephone', 'email'):
        if client.get(key):
            cl_lines.append(escape(str(client[key]).replace('\n', ' ')))
    cl_html = '<br>'.join(cl_lines)
    party = (
        f'<div class="party">'
        f'<div class="blk"><div class="lbl">Émetteur</div>'
        f'<strong>{escape(str(ctx.get("entreprise_nom", "") or ""))}</strong>'
        f'{("<br>" + meta_html) if meta_html else ""}</div>'
        f'<div class="blk" style="text-align:right;">'
        f'<div class="lbl">Client</div><strong>{cl_nom}</strong>'
        f'{("<br>" + cl_html) if cl_html else ""}</div></div>'
    )

    # Identité système.
    sys_rows = [('Référence du système', system.get('reference') or '—')]
    if system.get('puissance_kwc') is not None:
        sys_rows.append(('Puissance installée',
                         f"{_fr_num(system['puissance_kwc'], 2)} kWc"))
    if system.get('type_installation'):
        sys_rows.append(('Type', system['type_installation']))
    site = ', '.join(p for p in (system.get('site_adresse'),
                                 system.get('site_ville')) if p)
    if site:
        sys_rows.append(('Site', site))
    if system.get('date_mise_en_service'):
        sys_rows.append(('Mise en service', system['date_mise_en_service']))
    sys_html = ''.join(
        f'<tr><td>{escape(str(k))}</td><td class="v">{escape(str(v))}</td></tr>'
        for k, v in sys_rows)

    # Période.
    periode_txt = period.get('label') or f"{_fr_num(est['nb_mois'], 2)} mois"

    # Hypothèses (toutes « estimations »).
    base_prod = (
        "Production annuelle saisie manuellement"
        if est['production_manuelle']
        else (f"{_fr_num(est['puissance_kwc'], 2)} kWc × "
              f"{_fr_num(est['rendement_kwh_par_kwc_an'])} kWh/kWc/an"))
    hyp_rows = [
        ('Base de production (estimation)', base_prod),
        ('Production annuelle de référence',
         f"{_fr_num(est['production_annuelle_kwh'])} kWh/an"),
        ('Période considérée', periode_txt),
        ('Tarif électricité (hypothèse)',
         f"{_fr_num(est['tarif_mad_par_kwh'], 2)} MAD/kWh"),
        ('Facteur CO₂ réseau (hypothèse)',
         f"{_fr_num(est['co2_kg_par_kwh'], 3)} kg CO₂/kWh"),
    ]
    if not est['production_manuelle']:
        hyp_rows.insert(1, ('Rendement spécifique (hypothèse)',
                            f"{_fr_num(est['rendement_kwh_par_kwc_an'])} "
                            f"kWh/kWc/an"))
    hyp_html = ''.join(
        f'<tr><td>{escape(str(k))}</td><td class="v">{escape(str(v))}</td></tr>'
        for k, v in hyp_rows)

    # Cartes résultats.
    cards = (
        f'<div class="cards">'
        f'<div class="card"><div class="k">Production estimée</div>'
        f'<div class="big">{_fr_num(est["production_kwh"])}</div>'
        f'<div class="u">kWh sur la période</div></div>'
        f'<div class="card"><div class="k">Économies estimées</div>'
        f'<div class="big">{_fr_num(est["economies_mad"], 2)}</div>'
        f'<div class="u">MAD sur la période</div></div>'
        f'<div class="card"><div class="k">CO₂ évité (estimé)</div>'
        f'<div class="big">{_fr_num(est["co2_tonnes"], 3)}</div>'
        f'<div class="u">tonnes ({_fr_num(est["co2_kg"])} kg)</div></div>'
        f'</div>'
    )

    footer = (
        '<div class="ftr">Document indicatif — toutes les valeurs sont des '
        'ESTIMATIONS calculées à partir de la puissance nominale et '
        'd\'hypothèses d\'ensoleillement / de tarif, et non de mesures réelles '
        'de production. Les résultats effectifs peuvent varier.'
        f'<br>Édité le {escape(today)} · '
        f'{escape(str(ctx.get("entreprise_nom", "") or ""))}</div>'
    )

    body = (
        header
        + '<span class="estim">ESTIMATION — données non mesurées</span>'
        + '<h1>Rapport de production énergétique</h1>'
        + f'<div class="subtitle">Estimation pour la période : '
          f'{escape(periode_txt)} · Édité le {escape(today)}</div>'
        + party
        + '<div class="section-h">Système installé</div>'
          f'<table>{sys_html}</table>'
        + '<div class="section-h">Résultats estimés</div>'
          + cards
        + '<div class="section-h">Hypothèses de calcul (estimations)</div>'
          f'<table>{hyp_html}</table>'
        + footer
    )
    return (
        f'<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
        f'<title>Rapport de production — {escape(str(system.get("reference") or ""))}'
        f'</title><style>{_PAGE_CSS}</style></head><body>{body}</body></html>'
    )


def render_energy_report_pdf(installation, params):
    """Octets PDF du rapport de production estimée pour `installation`.

    `params` : dict des surcharges (mêmes clés que compute_energy_estimate, plus
    `date_debut`/`date_fin` en objets date). L'identité société vient de
    CompanyProfile (multi-tenant) ; le client vient du chantier. Aucun prix
    d'achat n'est lu — strictement client-facing.
    """
    from apps.ventes.utils.pdf import _company_context, _html_to_pdf

    est = compute_energy_estimate(
        installation.puissance_installee_kwc,
        nb_mois=params.get('nb_mois'),
        date_debut=params.get('date_debut'),
        date_fin=params.get('date_fin'),
        production_annuelle_kwh=params.get('production_annuelle_kwh'),
        rendement_kwh_par_kwc_an=params.get('rendement_kwh_par_kwc_an'),
        tarif_mad_par_kwh=params.get('tarif_mad_par_kwh'),
        co2_kg_par_kwh=params.get('co2_kg_par_kwh'),
    )

    ctx = _company_context(company=installation.company)

    client_obj = getattr(installation, 'client', None)
    client = {
        'nom': getattr(client_obj, 'nom', '') or '' if client_obj else '',
        'prenom': (getattr(client_obj, 'prenom', '') or '') if client_obj else '',
        'email': (getattr(client_obj, 'email', '') or '') if client_obj else '',
        'telephone': (getattr(client_obj, 'telephone', '') or '') if client_obj else '',
        'adresse': (getattr(client_obj, 'adresse', '') or '') if client_obj else '',
    }

    type_label = (installation.get_type_installation_display()
                  if getattr(installation, 'type_installation', None) else None)
    system = {
        'reference': installation.reference,
        'puissance_kwc': installation.puissance_installee_kwc,
        'type_installation': type_label,
        'site_adresse': installation.site_adresse,
        'site_ville': installation.site_ville,
        'date_mise_en_service': _fr_date(installation.date_mise_en_service),
    }

    # Libellé de période lisible : dates si fournies, sinon « N mois ».
    debut = params.get('date_debut')
    fin = params.get('date_fin')
    if isinstance(debut, date) and isinstance(fin, date) and fin >= debut:
        label = f"du {_fr_date(debut)} au {_fr_date(fin)}"
    else:
        label = f"{_fr_num(est['nb_mois'], 2)} mois"
    period = {'label': label}

    html = build_energy_report_html(ctx, system, client, est, period)
    return _html_to_pdf(html)
