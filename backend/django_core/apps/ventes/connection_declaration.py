"""FG272 — Générateur de déclaration de raccordement BT/MT (pré-remplissage).

Pré-remplit une demande/déclaration de raccordement (client / site / kWc /
onduleur / schéma) à partir d'un ``Devis`` (lignes + ``etude_params``) et, en
lecture seule, du chantier lié (via le sélecteur cross-app
``installations.selectors.installation_for_devis`` — JAMAIS d'import du modèle
installations). Réutilise ``diagram_params_from_devis`` (FG252) pour la partie
schéma/onduleur/kWc et ``regulatory_docs`` (FG267) pour la liste des pièces.

RULE #4 : ce document de raccordement est un document RÉGLEMENTAIRE, distinct du
PDF de DEVIS client — ``/proposal`` reste l'unique chemin du PDF de devis et le
moteur premium n'est pas touché. La génération PDF ici est un rendu HTML
autonome (WeasyPrint, déjà dépendance) ; aucun prix d'achat / marge n'apparaît.

Cœur PUR : ``build_declaration_data`` ne lit que des objets fournis et ne change
aucun statut de devis.
"""
from __future__ import annotations

from html import escape


def _client_block(client):
    """Bloc identité client depuis ``crm.Client`` (best-effort, lecture)."""
    if client is None:
        return {'nom': '', 'adresse': '', 'telephone': '', 'email': '',
                'ice': ''}
    nom = client.nom or ''
    prenom = getattr(client, 'prenom', '') or ''
    if prenom:
        nom = f'{nom} {prenom}'.strip()
    return {
        'nom': nom,
        'adresse': getattr(client, 'adresse', '') or '',
        'telephone': getattr(client, 'telephone', '') or '',
        'email': getattr(client, 'email', '') or '',
        'ice': getattr(client, 'ice', '') or '',
    }


def _site_block(chantier):
    """Bloc site/chantier (lecture seule). ``chantier`` peut être None."""
    if chantier is None:
        return {'reference': '', 'gps_lat': None, 'gps_lng': None,
                'date_mise_en_service': None}
    return {
        'reference': getattr(chantier, 'reference', '') or '',
        'gps_lat': getattr(chantier, 'gps_lat', None),
        'gps_lng': getattr(chantier, 'gps_lng', None),
        'date_mise_en_service': getattr(
            chantier, 'date_mise_en_service', None),
    }


def build_declaration_data(devis, *, chantier=None, diagram_params=None,
                           regime_8221=None):
    """FG272 — données pré-remplies d'une déclaration de raccordement.

    Paramètres
    ----------
    devis : ``ventes.Devis`` (avec ``client``, ``lignes``, ``etude_params``).
    chantier : objet chantier (lecture seule) ou None — fourni par l'appelant
        via le sélecteur cross-app, jamais importé ici.
    diagram_params : dict déjà calculé (``diagram_params_from_devis``) ou None
        (calculé à la demande).
    regime_8221 : code régime pour la liste des pièces (optionnel).

    Retourne un dict JSON-sérialisable ; ne lève pas sur données partielles.
    """
    from .single_line_diagram import diagram_params_from_devis
    from . import regulatory_docs

    if diagram_params is None:
        try:
            diagram_params = diagram_params_from_devis(devis)
        except Exception:
            diagram_params = {}

    etude = getattr(devis, 'etude_params', None) or {}
    # kWc : priorité au schéma déduit, repli sur etude_params.
    n_panneaux = diagram_params.get('n_panneaux') or 0
    wc = diagram_params.get('puissance_panneau_wc') or 0
    kwc = round((n_panneaux * wc) / 1000.0, 2) if (n_panneaux and wc) else None
    if kwc is None:
        for key in ('puissance_kwc', 'kwc'):
            if etude.get(key):
                try:
                    kwc = round(float(etude.get(key)), 2)
                    break
                except (TypeError, ValueError):
                    pass

    phases = diagram_params.get('phases') or 1
    raccordement = 'MT' if phases == 3 and (kwc or 0) >= 50 else 'BT'

    pieces = (regulatory_docs.required_documents(regime_8221)
              if regime_8221 else [])

    return {
        'devis_reference': getattr(devis, 'reference', '') or '',
        'client': _client_block(getattr(devis, 'client', None)),
        'site': _site_block(chantier),
        'systeme': {
            'kwc': kwc,
            'n_panneaux': n_panneaux,
            'puissance_panneau_wc': wc,
            'onduleur': diagram_params.get('onduleur') or '',
            'puissance_onduleur_kw':
                diagram_params.get('puissance_onduleur_kw') or 0,
            'phases': phases,
            'injection': bool(diagram_params.get('injection', True)),
            'has_battery': bool(diagram_params.get('has_battery', False)),
        },
        'raccordement': raccordement,
        'regime_8221': (regime_8221 or '').strip(),
        'regime_label': (regulatory_docs.regime_label(regime_8221)
                         if regime_8221 else ''),
        'pieces': pieces,
    }


def render_declaration_html(data):
    """FG272 — rend la déclaration pré-remplie en HTML autonome.

    HTML simple et autonome (aucun template du moteur premium) destiné à
    WeasyPrint. Jamais de prix. ``data`` = sortie de ``build_declaration_data``.
    """
    c = data.get('client', {})
    s = data.get('site', {})
    sys_ = data.get('systeme', {})

    def row(label, value):
        return (f'<tr><th>{escape(str(label))}</th>'
                f'<td>{escape(str(value if value not in (None, "") else "—"))}'
                f'</td></tr>')

    pieces_html = ''.join(
        f'<li>{escape(p.get("label", ""))}'
        f'{" (obligatoire)" if p.get("required") else ""}</li>'
        for p in data.get('pieces', []))
    pieces_block = (f'<h2>Pièces à joindre</h2><ul>{pieces_html}</ul>'
                    if pieces_html else '')

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 12px; color: #1a1a1a; }}
  h1 {{ font-size: 18px; }} h2 {{ font-size: 14px; margin-top: 16px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
  th {{ background: #f3f4f6; width: 38%; }}
</style></head><body>
<h1>Demande de raccordement {escape(str(data.get('raccordement', 'BT')))}</h1>
<p>Devis de référence : {escape(str(data.get('devis_reference', '')))}
 — Régime : {escape(str(data.get('regime_label') or '—'))}</p>
<h2>Client</h2>
<table>
{row('Nom / Raison sociale', c.get('nom'))}
{row('Adresse', c.get('adresse'))}
{row('Téléphone', c.get('telephone'))}
{row('Email', c.get('email'))}
{row('ICE', c.get('ice'))}
</table>
<h2>Site</h2>
<table>
{row('Référence chantier', s.get('reference'))}
{row('GPS', f"{s.get('gps_lat')}, {s.get('gps_lng')}"
     if s.get('gps_lat') else '')}
{row('Mise en service prévue', s.get('date_mise_en_service'))}
</table>
<h2>Installation PV</h2>
<table>
{row('Puissance crête (kWc)', sys_.get('kwc'))}
{row('Nombre de panneaux', sys_.get('n_panneaux'))}
{row('Onduleur', sys_.get('onduleur'))}
{row('Puissance onduleur (kW)', sys_.get('puissance_onduleur_kw'))}
{row('Phases', sys_.get('phases'))}
{row('Injection réseau', 'Oui' if sys_.get('injection') else 'Non')}
{row('Stockage batterie', 'Oui' if sys_.get('has_battery') else 'Non')}
</table>
{pieces_block}
</body></html>"""


def render_declaration_pdf(data):
    """Rend la déclaration en PDF (WeasyPrint). Import paresseux/protégé."""
    import weasyprint
    from io import BytesIO
    buf = BytesIO()
    weasyprint.HTML(string=render_declaration_html(data)).write_pdf(buf)
    buf.seek(0)
    return buf.read()
