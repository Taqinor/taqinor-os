"""XACC35 — Attestations de retenue à la source (RAS) par prestataire (PDF).

FG139 calcule la RAS et produit le bordereau de versement, FG143 l'état
annuel 9421, mais aucune attestation INDIVIDUELLE n'était remise au
prestataire (pièce que le fournisseur exige pour sa propre déclaration).

Rendu HTML → PDF via WeasyPrint (moteur légal existant — le même que
``apps.paie.builders`` — PAS le moteur de devis premium ; règle #4 du
CLAUDE.md non concernée : ceci n'est ni un devis ni un PDF client-facing de
vente). Self-contained : ce module ne lit que des champs PUBLICS
(``RetenueSource`` + ``CompanyProfile``, une app foundation exemptée de la
règle cross-app), jamais de donnée d'achat/marge.

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()`` + import
paresseux) est déléguée au service partagé ``core.pdf.render_pdf`` ; les
GABARITS HTML ci-dessous restent STRICTEMENT identiques (aucune option de
branding de ``render_pdf`` activée), donc le rendu est inchangé à l'octet
près.
"""
from datetime import date
from decimal import Decimal
from html import escape

from core.pdf import render_pdf

MOIS_FR = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def _fmt(montant):
    """Formate un Decimal en montant lisible « 1 234,56 » (espace milliers)."""
    montant = Decimal(montant or 0).quantize(Decimal('0.01'))
    entier, _, dec = f'{montant:.2f}'.partition('.')
    signe = ''
    if entier.startswith('-'):
        signe = '-'
        entier = entier[1:]
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return f"{signe}{' '.join(groupes)},{dec}"


def _entete_societe_html(company_profile):
    """Bloc entête société (raison sociale, ICE/IF/RC) commun aux deux PDFs."""
    if company_profile is None:
        return ''
    nom = escape(getattr(company_profile, 'nom', '') or '')
    ice = escape(getattr(company_profile, 'ice', '') or '')
    if_fiscal = escape(getattr(company_profile, 'identifiant_fiscal', '') or '')
    rc = escape(getattr(company_profile, 'rc', '') or '')
    lignes_id = []
    if ice:
        lignes_id.append(f'ICE : {ice}')
    if if_fiscal:
        lignes_id.append(f'IF : {if_fiscal}')
    if rc:
        lignes_id.append(f'RC : {rc}')
    identifiants = ' &nbsp;|&nbsp; '.join(lignes_id)
    return f"""
    <div class="entete">
      <div class="raison-sociale">{nom}</div>
      {f'<div class="identifiants">{identifiants}</div>' if identifiants else ''}
    </div>"""


_STYLE = """
  body { font-family: sans-serif; font-size: 12px; color: #222; margin: 40px; }
  h1 { font-size: 18px; text-align: center; margin-top: 24px; }
  .entete { text-align: center; border-bottom: 2px solid #444; padding-bottom: 10px; margin-bottom: 20px; }
  .raison-sociale { font-size: 16px; font-weight: bold; }
  .identifiants { font-size: 11px; color: #555; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; }
  th { background: #f2f2f2; }
  .total { font-weight: bold; font-size: 13px; margin-top: 12px; }
  .date { text-align: right; margin-top: 40px; }
"""


def render_attestation_retenue_html(retenue, company_profile=None, *,
                                    today=None):
    """HTML de l'attestation d'UN versement de RAS (XACC35).

    Reprend le snapshot figé de la ``RetenueSource`` (base/taux/montant/
    période) — jamais un recalcul. ``company_profile`` est le
    ``CompanyProfile`` de la société (entête). Renvoie le HTML.
    """
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    tiers_nom = escape(retenue.tiers_nom or '')
    identifiant_tiers = escape(retenue.identifiant_fiscal or '')
    piece = escape(retenue.piece or '')
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  {entete}
  <h1>Attestation de retenue à la source</h1>
  <p>Nous soussignés attestons avoir opéré, sur la pièce/prestation
  ci-dessous réglée à <strong>{tiers_nom}</strong>
  {f'(IF/ICE : {identifiant_tiers})' if identifiant_tiers else ''},
  la retenue à la source suivante :</p>
  <table>
    <thead><tr><th>Pièce</th><th>Date</th><th>Base (MAD)</th>
    <th>Taux</th><th>Montant retenu (MAD)</th></tr></thead>
    <tbody><tr>
      <td>{piece or '—'}</td>
      <td>{retenue.date_piece.strftime('%d/%m/%Y')}</td>
      <td>{_fmt(retenue.base)}</td>
      <td>{retenue.taux} %</td>
      <td>{_fmt(retenue.montant)}</td>
    </tr></tbody>
  </table>
  <p class="total">Montant retenu : {_fmt(retenue.montant)} MAD</p>
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_attestation_retenue_pdf(retenue, company_profile=None, *,
                                   today=None):
    """Attestation d'un versement → octets PDF (XACC35)."""
    return render_pdf(
        html=render_attestation_retenue_html(
            retenue, company_profile, today=today))


def render_attestation_annuelle_html(retenues, tiers_nom, annee,
                                     company_profile=None, *, today=None):
    """HTML du cumul ANNUEL de RAS pour un prestataire (XACC35).

    ``retenues`` est l'itérable de ``RetenueSource`` du tiers pour ``annee``
    (résolu côté appelant, snapshot figé). Renvoie le HTML avec le détail par
    pièce + le total cumulé.
    """
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    lignes = list(retenues)
    total = sum((Decimal(r.montant or 0) for r in lignes), Decimal('0'))
    total_base = sum((Decimal(r.base or 0) for r in lignes), Decimal('0'))
    rows = ''.join(
        f"<tr><td>{escape(r.piece or '—')}</td>"
        f"<td>{r.date_piece.strftime('%d/%m/%Y')}</td>"
        f"<td>{_fmt(r.base)}</td><td>{r.taux} %</td>"
        f"<td>{_fmt(r.montant)}</td></tr>"
        for r in lignes
    )
    identifiant_tiers = escape(
        lignes[0].identifiant_fiscal if lignes else '')
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  {entete}
  <h1>Attestation annuelle de retenue à la source — {annee}</h1>
  <p>Cumul des retenues à la source opérées au titre de l'exercice
  <strong>{annee}</strong> sur les prestations réglées à
  <strong>{escape(tiers_nom or '')}</strong>
  {f'(IF/ICE : {identifiant_tiers})' if identifiant_tiers else ''}.</p>
  <table>
    <thead><tr><th>Pièce</th><th>Date</th><th>Base (MAD)</th>
    <th>Taux</th><th>Montant retenu (MAD)</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="total">Total base : {_fmt(total_base)} MAD &nbsp;|&nbsp;
  Total retenu {annee} : {_fmt(total)} MAD</p>
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_attestation_annuelle_pdf(retenues, tiers_nom, annee,
                                    company_profile=None, *, today=None):
    """Cumul annuel → octets PDF (XACC35)."""
    return render_pdf(
        html=render_attestation_annuelle_html(
            retenues, tiers_nom, annee, company_profile, today=today))
