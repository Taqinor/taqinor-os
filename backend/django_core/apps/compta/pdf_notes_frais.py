"""ZACC8 — Attestation / reçu PDF de remboursement de note de frais.

La validation/le remboursement d'une ``NoteFrais`` ne produisait AUCUN
document remis à l'employé (le reçu client XFAC9 est côté ventes, pas côté
frais). Ce module ajoute un reçu WeasyPrint sobre (même moteur légal que
``pdf_ras.py``/``pdf_etats.py`` — PAS le quote engine premium ; règle #4 du
CLAUDE.md non concernée) : entête société, employé, détail des lignes,
total remboursé en chiffres ET en lettres (FR), mode/date de remboursement,
référence écriture. JAMAIS aucun prix d'achat/marge.

``montant_en_lettres`` est RÉUTILISÉ depuis ``apps.ventes.utils.
nombre_lettres`` (XFAC9, même conversion français/MAD que la quittance de
paiement) — aucune réimplémentation ; l'import cross-app d'un module
``utils`` (pas de ``models``/``views``) suit le même patron déjà en place
pour ``apps.ventes.utils.references``.

ARC11 — la plomberie WeasyPrint est déléguée au service partagé
``core.pdf.render_pdf`` ; les GABARITS HTML ci-dessous (dont l'en-tête société
``_entete_societe_html``) restent STRICTEMENT identiques (aucune option de
branding de ``render_pdf`` activée), donc le rendu est inchangé à l'octet près.
"""
from datetime import date
from decimal import Decimal
from html import escape

from apps.ventes.utils.nombre_lettres import montant_en_lettres
from core.pdf import render_pdf

MOIS_FR = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def _fmt(montant):
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
  .entete { text-align: center; border-bottom: 2px solid #444;
            padding-bottom: 10px; margin-bottom: 20px; }
  .raison-sociale { font-size: 16px; font-weight: bold; }
  .identifiants { font-size: 11px; color: #555; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; }
  td.montant, th.montant { text-align: right; font-variant-numeric: tabular-nums; }
  th { background: #f2f2f2; }
  .total { font-weight: bold; font-size: 13px; margin-top: 12px; }
  .lettres { font-style: italic; margin-top: 4px; }
  .date { text-align: right; margin-top: 40px; }
"""


def render_recu_note_frais_html(note, company_profile=None, *, today=None):
    """HTML du reçu de remboursement d'UNE ``NoteFrais`` (ZACC8).

    Reprend le snapshot figé de la note (jamais un recalcul) : catégorie,
    date, montant. Lève ``ValueError`` si la note n'est pas remboursée
    (contrôle métier fait côté vue — ici on suppose l'appelant a déjà
    vérifié)."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    employe_nom = escape(
        getattr(note.employe, 'get_full_name', lambda: '')() or
        getattr(note.employe, 'username', '') or '')
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  {entete}
  <h1>Reçu de remboursement de note de frais</h1>
  <p>Remboursement versé à <strong>{employe_nom}</strong>.</p>
  <table>
    <thead><tr><th>Date</th><th>Catégorie</th><th>Motif</th>
    <th class="montant">Montant (MAD)</th></tr></thead>
    <tbody><tr>
      <td>{note.date_frais.strftime('%d/%m/%Y')}</td>
      <td>{escape(note.get_categorie_display())}</td>
      <td>{escape(note.motif or '')}</td>
      <td class="montant">{_fmt(note.montant)}</td>
    </tr></tbody>
  </table>
  <p class="total">Total remboursé : {_fmt(note.montant)} MAD</p>
  <p class="lettres">Arrêtée la présente somme à {montant_en_lettres(note.montant)}.</p>
  <p>Mode de remboursement : {escape(note.get_mode_remboursement_display())}
  &nbsp;|&nbsp; Date : {
      note.date_remboursement.strftime('%d/%m/%Y')
      if note.date_remboursement else '—'}
  &nbsp;|&nbsp; Référence écriture : {
      escape(note.ecriture_remboursement.reference)
      if note.ecriture_remboursement
      and note.ecriture_remboursement.reference else '—'}</p>
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_recu_note_frais_pdf(note, company_profile=None, *, today=None):
    return render_pdf(
        html=render_recu_note_frais_html(note, company_profile, today=today))


def render_recu_rapport_note_frais_html(rapport, company_profile=None, *,
                                        today=None):
    """HTML du reçu de remboursement d'UN ``RapportNoteFrais`` (ZACC8 +
    ZACC6) : détail de CHAQUE note rattachée + total en chiffres ET en
    lettres."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    employe_nom = escape(
        getattr(rapport.employe, 'get_full_name', lambda: '')() or
        getattr(rapport.employe, 'username', '') or '')
    notes = list(rapport.notes.all().order_by('date_frais', 'id'))
    total = sum((Decimal(n.montant or 0) for n in notes), Decimal('0'))
    rows = ''.join(
        f"<tr><td>{n.date_frais.strftime('%d/%m/%Y')}</td>"
        f"<td>{escape(n.get_categorie_display())}</td>"
        f"<td>{escape(n.motif or '')}</td>"
        f"<td class=\"montant\">{_fmt(n.montant)}</td></tr>"
        for n in notes
    )
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  {entete}
  <h1>Reçu de remboursement — rapport de notes de frais</h1>
  <p>Rapport <strong>{escape(rapport.reference or '')}</strong> remboursé à
  <strong>{employe_nom}</strong>.</p>
  <table>
    <thead><tr><th>Date</th><th>Catégorie</th><th>Motif</th>
    <th class="montant">Montant (MAD)</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="total">Total remboursé : {_fmt(total)} MAD</p>
  <p class="lettres">Arrêtée la présente somme à {montant_en_lettres(total)}.</p>
  <p>Mode de remboursement :
  {escape(rapport.get_mode_remboursement_display())}
  &nbsp;|&nbsp; Date : {
      rapport.date_remboursement.strftime('%d/%m/%Y')
      if rapport.date_remboursement else '—'}
  &nbsp;|&nbsp; Référence écriture : {
      escape(rapport.ecriture_remboursement.reference)
      if rapport.ecriture_remboursement
      and rapport.ecriture_remboursement.reference else '—'}</p>
  <p class="date">Fait le {escape(date_txt)}.</p>
</body></html>"""


def render_recu_rapport_note_frais_pdf(rapport, company_profile=None, *,
                                       today=None):
    return render_pdf(
        html=render_recu_rapport_note_frais_html(
            rapport, company_profile, today=today))
