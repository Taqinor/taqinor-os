"""Rendu PDF du module Immobilier — via le service partagé ``core.pdf``
(ARC11), JAMAIS le moteur premium ``/proposal`` (règle #4 CLAUDE.md, réservé
aux devis client). La quittance est un document DISTINCT de la facture ventes
(un accusé de paiement simple), rendu à la volée (non stocké)."""
import html as _html

from core.pdf import render_pdf


def _esc(value):
    """Échappe le texte utilisateur injecté dans le HTML (jamais de jeton
    brut, jamais d'injection HTML depuis un champ libre)."""
    if value is None:
        return ''
    return _html.escape(str(value))


_CSS = (
    "body{font-family:'Liberation Sans',sans-serif;font-size:11pt;"
    "color:#1a1a1a;margin:1.5cm;line-height:1.5;}"
    "h1{font-size:16pt;border-bottom:2px solid #2b5cab;padding-bottom:6px;}"
    "table{width:100%;border-collapse:collapse;margin-top:10px;}"
    "td,th{border:1px solid #999;padding:5px 8px;text-align:left;}"
    ".label{font-weight:bold;width:220px;}"
    ".montant{font-size:13pt;font-weight:bold;}"
)


def _html_shell(title, body):
    return (
        "<html lang='fr'><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def render_quittance_pdf(echeance):
    """NTPRO7 — PDF « quittance de loyer » (accusé de paiement simple).

    ``echeance`` = ``EcheanceLoyer`` déjà émise (``facture_ventes_id`` posé) —
    affiche période / local / locataire / montant. Document INTERNE distinct
    de la facture ventes ; jamais le moteur ``/proposal`` (règle #4)."""
    bail = echeance.bail
    local = bail.local
    locataire = bail.locataire

    body = (
        "<h1>Quittance de loyer</h1>"
        "<table>"
        f"<tr><td class='label'>Période</td>"
        f"<td>{_esc(echeance.periode_debut)} — {_esc(echeance.periode_fin)}</td></tr>"
        f"<tr><td class='label'>Local</td>"
        f"<td>{_esc(local.reference)} ({_esc(local.niveau.batiment.nom)})</td></tr>"
        f"<tr><td class='label'>Locataire</td>"
        f"<td>{_esc(locataire.nom)}</td></tr>"
        f"<tr><td class='label'>Loyer HT</td>"
        f"<td>{_esc(echeance.montant_loyer_ht)} MAD</td></tr>"
        f"<tr><td class='label'>Charges</td>"
        f"<td>{_esc(echeance.montant_charges)} MAD</td></tr>"
        f"<tr><td class='label montant'>Montant total</td>"
        f"<td class='montant'>{_esc(echeance.montant_total)} MAD</td></tr>"
        f"<tr><td class='label'>Référence facture</td>"
        f"<td>{_esc(echeance.facture_ventes_id or '—')}</td></tr>"
        "</table>"
    )
    html = _html_shell('Quittance de loyer', body)
    return render_pdf(html=html, company=bail.company, footer=True)
