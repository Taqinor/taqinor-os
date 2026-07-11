"""ZACC1 — Rendu PDF imprimable des états de synthèse & légaux.

``apps/compta/views.py`` ne portait AUCUN rendu WeasyPrint (les états
UX5/UX7 — bilan/CPC/balance/grand livre/liasse/balance âgée — ne sortaient
qu'en JSON + xlsx/csv). Un cabinet/une banque/la DGI exigent un PDF
signable, entête société. Ce module ajoute un rendu PDF LÉGAL générique
(mêmes principes que ``pdf_ras.py`` : moteur WeasyPrint existant, PAS le
quote engine premium — règle #4 du CLAUDE.md non concernée : ceci n'est ni
un devis ni un PDF client-facing de vente).

Chaque fonction ``render_*_pdf`` prend le dict DÉJÀ calculé par le sélecteur
correspondant (aucun recalcul) + le ``CompanyProfile`` (entête : raison
sociale, ICE/IF/RC) et l'exercice/période, et renvoie des octets PDF.

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


def _html_to_pdf(html_string):
    """ARC12 — shim de compat : délègue au service PDF partagé
    (``core.pdf.render_pdf``). Trois appelants dans ``apps/compta/views.py``
    (ZACC3 tableau_flux, ZACC12 tableau_immobilisations, ZACC10 bordereau_pdf)
    construisent leur fragment HTML directement dans la vue et importent ce
    helper — le refactor ARC12 avait recâblé les 6 renderers ``render_*_pdf``
    de CE module vers ``render_pdf`` mais supprimé ce seam sans le réexporter,
    d'où un ``ImportError`` (NON attrapé par ``_pdf_or_503`` qui ne gère que
    ``RuntimeError``). ``render_pdf`` conserve le contrat ``RuntimeError`` si
    WeasyPrint est absent, donc la dégradation gracieuse 503 refonctionne."""
    return render_pdf(html=html_string)


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
    """Bloc entête société (raison sociale, ICE/IF/RC/patente) commun."""
    if company_profile is None:
        return ''
    nom = escape(getattr(company_profile, 'nom', '') or '')
    ice = escape(getattr(company_profile, 'ice', '') or '')
    if_fiscal = escape(getattr(company_profile, 'identifiant_fiscal', '') or '')
    rc = escape(getattr(company_profile, 'rc', '') or '')
    patente = escape(getattr(company_profile, 'patente', '') or '')
    lignes_id = []
    if ice:
        lignes_id.append(f'ICE : {ice}')
    if if_fiscal:
        lignes_id.append(f'IF : {if_fiscal}')
    if rc:
        lignes_id.append(f'RC : {rc}')
    if patente:
        lignes_id.append(f'Patente : {patente}')
    identifiants = ' &nbsp;|&nbsp; '.join(lignes_id)
    return f"""
    <div class="entete">
      <div class="raison-sociale">{nom}</div>
      {f'<div class="identifiants">{identifiants}</div>' if identifiants else ''}
    </div>"""


_STYLE = """
  body { font-family: sans-serif; font-size: 12px; color: #222; margin: 36px; }
  h1 { font-size: 17px; text-align: center; margin-top: 20px; }
  h2 { font-size: 13px; margin-top: 22px; border-bottom: 1px solid #999; }
  .entete { text-align: center; border-bottom: 2px solid #444;
            padding-bottom: 10px; margin-bottom: 18px; }
  .raison-sociale { font-size: 16px; font-weight: bold; }
  .identifiants { font-size: 11px; color: #555; margin-top: 4px; }
  .periode { text-align: center; font-size: 11px; color: #444; margin-bottom: 10px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { border: 1px solid #ccc; padding: 4px 7px; text-align: left; }
  td.montant, th.montant { text-align: right; font-variant-numeric: tabular-nums; }
  th { background: #f2f2f2; }
  .total-row td { font-weight: bold; background: #fafafa; }
  .mention { font-size: 10px; color: #666; margin-top: 24px; }
  .date { text-align: right; margin-top: 20px; font-size: 11px; }
"""


def _periode_txt(date_debut, date_fin):
    if date_debut and date_fin:
        return f'Période du {date_debut} au {date_fin}'
    if date_fin:
        return f'Arrêté au {date_fin}'
    return "Sur l'ensemble des données disponibles"


def _lignes_rows(lignes):
    return ''.join(
        f"<tr><td>{escape(str(item.get('numero', '')))}</td>"
        f"<td>{escape(str(item.get('intitule', '')))}</td>"
        f"<td class=\"montant\">{_fmt(item.get('montant'))}</td></tr>"
        for item in lignes
    )


def _wrap(entete, titre, periode_txt, corps, today):
    date_txt = f'{today.day} {MOIS_FR[today.month]} {today.year}'
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  {entete}
  <h1>{escape(titre)}</h1>
  <div class="periode">{escape(periode_txt)}</div>
  {corps}
  <p class="mention">État établi selon le CGNC (coût historique).</p>
  <p class="date">Arrêté le {escape(date_txt)}.</p>
</body></html>"""


def render_bilan_html(data, company_profile=None, *, date_fin=None,
                      today=None):
    """HTML du bilan (FG114/COMPTA28) depuis le dict déjà calculé."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    periode_txt = _periode_txt(None, date_fin)
    corps = f"""
    <h2>Actif</h2>
    <table><thead><tr><th>N°</th><th>Intitulé</th>
    <th class="montant">Montant</th></tr></thead>
    <tbody>{_lignes_rows(data['actif'])}
    <tr class="total-row"><td colspan="2">Total actif</td>
    <td class="montant">{_fmt(data['total_actif'])}</td></tr></tbody></table>
    <h2>Passif</h2>
    <table><thead><tr><th>N°</th><th>Intitulé</th>
    <th class="montant">Montant</th></tr></thead>
    <tbody>{_lignes_rows(data['passif'])}
    <tr class="total-row"><td colspan="2">Résultat de l'exercice</td>
    <td class="montant">{_fmt(data['resultat'])}</td></tr>
    <tr class="total-row"><td colspan="2">Total passif + résultat</td>
    <td class="montant">{_fmt(data['total_passif'] + data['resultat'])}
    </td></tr></tbody></table>"""
    return _wrap(entete, 'Bilan', periode_txt, corps, today)


def render_bilan_pdf(data, company_profile=None, *, date_fin=None, today=None):
    return render_pdf(
        html=render_bilan_html(
            data, company_profile, date_fin=date_fin, today=today))


def render_cpc_html(data, company_profile=None, *, date_debut=None,
                    date_fin=None, today=None):
    """HTML du CPC (état de résultat) depuis le dict déjà calculé."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    periode_txt = _periode_txt(date_debut, date_fin)
    corps = f"""
    <h2>Produits</h2>
    <table><thead><tr><th>N°</th><th>Intitulé</th>
    <th class="montant">Montant</th></tr></thead>
    <tbody>{_lignes_rows(data['produits'])}
    <tr class="total-row"><td colspan="2">Total produits</td>
    <td class="montant">{_fmt(data['total_produits'])}</td></tr></tbody></table>
    <h2>Charges</h2>
    <table><thead><tr><th>N°</th><th>Intitulé</th>
    <th class="montant">Montant</th></tr></thead>
    <tbody>{_lignes_rows(data['charges'])}
    <tr class="total-row"><td colspan="2">Total charges</td>
    <td class="montant">{_fmt(data['total_charges'])}</td></tr></tbody></table>
    <table><tbody><tr class="total-row">
    <td>Résultat net</td>
    <td class="montant">{_fmt(data['resultat'])}</td></tr></tbody></table>"""
    return _wrap(entete, 'Compte de produits et charges (CPC)', periode_txt,
                 corps, today)


def render_cpc_pdf(data, company_profile=None, *, date_debut=None,
                   date_fin=None, today=None):
    return render_pdf(
        html=render_cpc_html(
            data, company_profile, date_debut=date_debut,
            date_fin=date_fin, today=today))


def render_balance_html(data, company_profile=None, *, date_debut=None,
                        date_fin=None, today=None):
    """HTML de la balance générale depuis le dict déjà calculé
    (``selectors.balance_generale`` : clé ``lignes``, ``solde_debiteur``/
    ``solde_crediteur``)."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    periode_txt = _periode_txt(date_debut, date_fin)
    lignes = data.get('lignes', [])
    rows = ''.join(
        f"<tr><td>{escape(str(row.get('numero', '')))}</td>"
        f"<td>{escape(str(row.get('intitule', '')))}</td>"
        f"<td class=\"montant\">{_fmt(row.get('debit'))}</td>"
        f"<td class=\"montant\">{_fmt(row.get('credit'))}</td>"
        f"<td class=\"montant\">{_fmt(row.get('solde_debiteur'))}</td>"
        f"<td class=\"montant\">{_fmt(row.get('solde_crediteur'))}</td></tr>"
        for row in lignes
    )
    corps = f"""
    <table><thead><tr><th>N°</th><th>Intitulé</th>
    <th class="montant">Débit</th><th class="montant">Crédit</th>
    <th class="montant">Solde débiteur</th>
    <th class="montant">Solde créditeur</th></tr></thead>
    <tbody>{rows}
    <tr class="total-row"><td colspan="2">Totaux</td>
    <td class="montant">{_fmt(data.get('total_debit'))}</td>
    <td class="montant">{_fmt(data.get('total_credit'))}</td>
    <td class="montant" colspan="2"></td></tr></tbody></table>"""
    return _wrap(entete, 'Balance générale', periode_txt, corps, today)


def render_balance_pdf(data, company_profile=None, *, date_debut=None,
                       date_fin=None, today=None):
    return render_pdf(
        html=render_balance_html(
            data, company_profile, date_debut=date_debut,
            date_fin=date_fin, today=today))


def render_grand_livre_html(data, company_profile=None, *, date_debut=None,
                            date_fin=None, today=None):
    """HTML du grand livre depuis la LISTE déjà calculée par
    ``selectors.grand_livre`` (une entrée par compte, ``lignes[].date``)."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    periode_txt = _periode_txt(date_debut, date_fin)
    comptes = data if isinstance(data, list) else data.get('comptes', [])
    sections = []
    for compte in comptes:
        lignes = compte.get('lignes', [])
        rows = ''.join(
            f"<tr><td>{escape(str(li.get('date', '')))}</td>"
            f"<td>{escape(str(li.get('libelle', '')))}</td>"
            f"<td class=\"montant\">{_fmt(li.get('debit'))}</td>"
            f"<td class=\"montant\">{_fmt(li.get('credit'))}</td></tr>"
            for li in lignes
        )
        sections.append(f"""
        <h2>{escape(str(compte.get('numero', '')))} —
        {escape(str(compte.get('intitule', '')))}</h2>
        <table><thead><tr><th>Date</th><th>Libellé</th>
        <th class="montant">Débit</th><th class="montant">Crédit</th>
        </tr></thead><tbody>{rows}
        <tr class="total-row"><td colspan="2">Solde</td>
        <td class="montant" colspan="2">{_fmt(compte.get('solde'))}</td>
        </tr></tbody></table>""")
    corps = ''.join(sections) or '<p>Aucun mouvement sur la période.</p>'
    return _wrap(entete, 'Grand livre', periode_txt, corps, today)


def render_grand_livre_pdf(data, company_profile=None, *, date_debut=None,
                           date_fin=None, today=None):
    return render_pdf(
        html=render_grand_livre_html(
            data, company_profile, date_debut=date_debut,
            date_fin=date_fin, today=today))


def render_liasse_html(data, company_profile=None, *, exercice=None,
                       today=None):
    """HTML de la liasse fiscale (paquet bilan+CPC+balance+annexe TVA)."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    date_debut = getattr(exercice, 'date_debut', None)
    date_fin = getattr(exercice, 'date_fin', None)
    periode_txt = _periode_txt(date_debut, date_fin)
    corps = ''
    bilan_data = data.get('bilan')
    if bilan_data:
        corps += render_bilan_html(
            bilan_data, None, date_fin=date_fin, today=today
        ).split('<body>')[1].split('</body>')[0]
    cpc_data = data.get('cpc')
    if cpc_data:
        corps += render_cpc_html(
            cpc_data, None, date_debut=date_debut, date_fin=date_fin,
            today=today).split('<body>')[1].split('</body>')[0]
    return _wrap(entete, 'Liasse fiscale', periode_txt, corps, today)


def render_liasse_pdf(data, company_profile=None, *, exercice=None,
                      today=None):
    return render_pdf(
        html=render_liasse_html(
            data, company_profile, exercice=exercice, today=today))


def render_balance_agee_html(data, company_profile=None, *,
                             date_reference=None, today=None, titre=None):
    """HTML d'une balance âgée fournisseurs — buckets 0-30/31-60/61-90/90+
    (``selectors.balance_agee_fournisseurs`` : LISTE de dicts
    ``b0_30``/``b31_60``/``b61_90``/``b90_plus``/``total``/
    ``fournisseur_nom``)."""
    if today is None:
        today = date.today()
    entete = _entete_societe_html(company_profile)
    periode_txt = (f'Situation au {date_reference}' if date_reference
                   else "Situation à ce jour")
    lignes = data if isinstance(data, list) else data.get('lignes', [])
    total_general = sum(
        (Decimal(li.get('total') or 0) for li in lignes), Decimal('0'))
    rows = ''.join(
        f"<tr><td>{escape(str(li.get('fournisseur_nom', li.get('tiers_id', ''))))}"
        f"</td>"
        f"<td class=\"montant\">{_fmt(li.get('b0_30'))}</td>"
        f"<td class=\"montant\">{_fmt(li.get('b31_60'))}</td>"
        f"<td class=\"montant\">{_fmt(li.get('b61_90'))}</td>"
        f"<td class=\"montant\">{_fmt(li.get('b90_plus'))}</td>"
        f"<td class=\"montant\">{_fmt(li.get('total'))}</td></tr>"
        for li in lignes
    )
    corps = f"""
    <table><thead><tr><th>Fournisseur</th>
    <th class="montant">0-30j</th><th class="montant">31-60j</th>
    <th class="montant">61-90j</th><th class="montant">90j+</th>
    <th class="montant">Total</th></tr></thead>
    <tbody>{rows}
    <tr class="total-row"><td>Total</td>
    <td class="montant" colspan="4"></td>
    <td class="montant">{_fmt(total_general)}</td></tr></tbody></table>"""
    return _wrap(entete, titre or 'Balance âgée fournisseurs', periode_txt,
                 corps, today)


def render_balance_agee_pdf(data, company_profile=None, *,
                            date_reference=None, today=None, titre=None):
    return render_pdf(
        html=render_balance_agee_html(
            data, company_profile, date_reference=date_reference,
            today=today, titre=titre))
