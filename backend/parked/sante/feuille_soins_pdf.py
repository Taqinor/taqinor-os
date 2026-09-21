"""NTSAN14 — Feuille de soins (FSE-like) imprimable, renderer DÉDIÉ.

PÉRIMÈTRE v1 : c'est un IMPRIMÉ récapitulatif (patient, praticien, actes +
codes, montants, convention) — PAS un flux électronique certifié CNOPS/CNSS.
Aucune transmission, aucune signature réglementaire : le document est remis au
patient ou classé, exactement comme la feuille papier qu'il remplace.

RÈGLE #4 (CLAUDE.md) : ce module n'importe RIEN de
``apps/ventes/quote_engine/`` — une feuille de soins n'est ni un devis client
ni la facture elle-même (la ``FactureSante`` garde son propre cycle). Le rendu
passe par le moteur PDF PARTAGÉ ``core.pdf.render_pdf`` (ARC11), jamais par un
import direct de ``weasyprint`` ni par un second moteur.

Gabarit brandé : l'en-tête (titre + texte d'introduction) peut être surchargé
PAR SOCIÉTÉ via le ``core.BrandedTemplate`` existant (``kind='pdf'``,
``code='feuille_soins'``) rendu par le moteur de placeholders SÛR
``core.templating`` — sans template, l'imprimé garde ses libellés par défaut.
"""
from html import escape

from core.pdf import render_pdf

# Code du ``BrandedTemplate`` (kind ``pdf``) qui surcharge l'en-tête.
BRANDED_TEMPLATE_CODE = 'feuille_soins'

TITRE_DEFAUT = 'Feuille de soins'
INTRODUCTION_DEFAUT = (
    'Récapitulatif des actes réalisés — document à conserver. Cet imprimé '
    "n'est pas une télétransmission certifiée.")

_STYLE = """
  body { font-family: sans-serif; margin: 40px; color: #1e293b; }
  h1 { font-size: 20px; margin: 0 0 6px 0; }
  .intro { font-size: 11px; color: #555; margin-bottom: 18px; }
  .blocs { width: 100%; font-size: 12px; margin-bottom: 16px; }
  .blocs td { vertical-align: top; padding-right: 24px; }
  .blocs .cle { color: #555; }
  table.actes { width: 100%; border-collapse: collapse; font-size: 12px; }
  table.actes th, table.actes td {
    border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
  table.actes th { background: #f1f5f9; }
  table.actes td.num, table.actes th.num { text-align: right; }
  .totaux { margin-top: 16px; font-size: 12px; }
  .totaux div { margin: 3px 0; }
  .totaux .fort { font-weight: bold; }
"""


def _montant(valeur):
    return f'{valeur:.2f}' if valeur is not None else '0.00'


def _lignes_actes_html(actes):
    """Une ligne PAR ACTE RÉALISÉ, avec son code (critère d'acceptation)."""
    if not actes:
        return '<tr><td colspan="6">Aucun acte facturé.</td></tr>'
    lignes = []
    for acte in actes:
        lignes.append(
            '<tr>'
            f'<td>{escape(str(acte.get("code", "") or "—"))}</td>'
            f'<td>{escape(str(acte.get("libelle", "")))}</td>'
            f'<td>{escape(str(acte.get("praticien", "") or "—"))}</td>'
            f'<td>{escape(str(acte.get("date", "") or ""))}</td>'
            f'<td class="num">{escape(str(acte.get("quantite", 1)))}</td>'
            f'<td class="num">{_montant(acte.get("montant_ttc"))}</td>'
            '</tr>')
    return ''.join(lignes)


def render_feuille_soins_html(contexte):
    """HTML de la feuille de soins à partir du contexte assemblé par
    ``services.imprimer_feuille_soins``."""
    titre = contexte.get('titre') or TITRE_DEFAUT
    intro = contexte.get('introduction') or INTRODUCTION_DEFAUT
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  <h1>{escape(str(titre))}</h1>
  <div class="intro">{escape(str(intro))}</div>
  <table class="blocs"><tr>
    <td>
      <div class="cle">Patient</div>
      <div><strong>{escape(str(contexte.get('patient', '')))}</strong></div>
      <div>N° dossier : {escape(str(contexte.get('numero_dossier', '') or '—'))}</div>
      <div>CIN : {escape(str(contexte.get('cin', '') or '—'))}</div>
    </td>
    <td>
      <div class="cle">Convention</div>
      <div>{escape(str(contexte.get('convention', '') or 'Aucune (cash)'))}</div>
      <div>N° affiliation :
      {escape(str(contexte.get('numero_affiliation', '') or '—'))}</div>
    </td>
    <td>
      <div class="cle">Facture</div>
      <div>N° {escape(str(contexte.get('facture_id', '')))}</div>
      <div>Statut : {escape(str(contexte.get('statut', '')))}</div>
    </td>
  </tr></table>
  <table class="actes">
    <thead><tr>
      <th>Code</th><th>Acte</th><th>Praticien</th><th>Date</th>
      <th class="num">Qté</th><th class="num">Montant TTC</th>
    </tr></thead>
    <tbody>{_lignes_actes_html(contexte.get('actes'))}</tbody>
  </table>
  <div class="totaux">
    <div>Sous-total TTC : {_montant(contexte.get('sous_total_ttc'))}</div>
    <div>Remise TTC : {_montant(contexte.get('remise_ttc'))}</div>
    <div class="fort">Total TTC : {_montant(contexte.get('total_ttc'))}</div>
    <div>Part tiers payant : {_montant(contexte.get('part_tiers_payant_ttc'))}</div>
    <div>Part patient (reste à charge) :
    {_montant(contexte.get('part_patient_ttc'))}</div>
  </div>
</body></html>"""


def render_feuille_soins_pdf(contexte):
    """Octets PDF de la feuille de soins — moteur PARTAGÉ ``core.pdf``."""
    return render_pdf(html=render_feuille_soins_html(contexte))
