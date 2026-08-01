"""NTEDU17 — Bulletin scolaire PDF, renderer DÉDIÉ.

RÈGLE #4 (CLAUDE.md) — ce module n'importe RIEN de
``apps/ventes/quote_engine/`` et n'y renvoie jamais : un bulletin scolaire
n'est pas un devis client, les deux documents n'ont aucun rôle commun. Le
chemin ``/proposal`` reste l'unique chemin des PDF de DEVIS client ; ce
renderer-ci vit dans son app et rend un document interne/famille.

Moteur : ``core.pdf.render_pdf`` (plomberie WeasyPrint PARTAGÉE d'ARC11 —
jamais un second moteur PDF, jamais un import direct de ``weasyprint`` ici),
exactement comme ``apps.education.certificat_pdf`` (NTEDU18).

Séparation des rôles : ce module ne fait QUE du rendu. Les données du bulletin
(moyennes pondérées par coefficient, rang, mention, présences de la période)
sont assemblées par ``apps.education.services.donnees_bulletin`` — ce qui rend
le calcul testable sans WeasyPrint installé.
"""
from html import escape

from core.pdf import render_pdf

_STYLE = """
  body { font-family: sans-serif; margin: 40px; color: #1e293b; }
  h1 { font-size: 20px; margin: 0 0 4px 0; }
  .sous-titre { font-size: 12px; color: #555; margin-bottom: 18px; }
  .identite { font-size: 12px; margin-bottom: 16px; }
  .identite span { margin-right: 18px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
  th { background: #f1f5f9; }
  td.num, th.num { text-align: right; }
  .synthese { margin-top: 18px; font-size: 12px; }
  .synthese div { margin: 4px 0; }
  .appreciation { margin-top: 18px; font-size: 12px; }
  .appreciation .cadre {
    border: 1px solid #cbd5e1; padding: 10px; min-height: 40px; }
  .signature { margin-top: 24px; font-size: 11px; color: #555; }
"""


def _fmt(valeur, suffixe=''):
    """Formate une moyenne/valeur décimale, ou « — » si absente."""
    if valeur is None:
        return '—'
    return f'{valeur:.2f}{suffixe}'


def _lignes_matieres_html(matieres):
    # `matieres` liste les matières CONFIGURÉES sur la classe, notées ou non :
    # une classe a presque toujours des matières, donc `if not matieres` ne se
    # déclenchait jamais et un élève sans aucune note obtenait un tableau de
    # lignes toutes à « — » au lieu de l'état vide. L'état vide dépend des
    # NOTES, pas de la présence de matières au programme.
    if not matieres or all(
            ligne.get('moyenne') is None for ligne in matieres):
        return (
            '<tr><td colspan="4">Aucune note saisie sur la période.</td></tr>')
    lignes = []
    for ligne in matieres:
        lignes.append(
            '<tr>'
            f'<td>{escape(str(ligne.get("matiere", "")))}</td>'
            f'<td class="num">{_fmt(ligne.get("coefficient"))}</td>'
            f'<td class="num">{_fmt(ligne.get("moyenne"))}</td>'
            f'<td>{escape(str(ligne.get("appreciation", "") or ""))}</td>'
            '</tr>')
    return ''.join(lignes)


def render_bulletin_html(contexte):
    """HTML du bulletin (NTEDU17) à partir du contexte de
    ``services.donnees_bulletin``."""
    presences = contexte.get('presences') or {}
    rang = contexte.get('rang')
    effectif = contexte.get('effectif_classe')
    rang_txt = (
        f'{rang} / {effectif}' if rang and effectif else '—')
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  <h1>Bulletin scolaire</h1>
  <div class="sous-titre">{escape(str(contexte.get('periode', '')))} —
  {escape(str(contexte.get('annee_scolaire', '')))}</div>
  <div class="identite">
    <span>Élève : <strong>{escape(str(contexte.get('eleve', '')))}</strong></span>
    <span>Classe : {escape(str(contexte.get('classe', '') or '—'))}</span>
    <span>N° dossier : {escape(str(contexte.get('numero_dossier', '') or '—'))}</span>
  </div>
  <table>
    <thead><tr>
      <th>Matière</th><th class="num">Coef.</th>
      <th class="num">Moyenne</th><th>Appréciation</th>
    </tr></thead>
    <tbody>{_lignes_matieres_html(contexte.get('matieres'))}</tbody>
  </table>
  <div class="synthese">
    <div>Moyenne générale : <strong>{_fmt(contexte.get('moyenne_generale'))}</strong>
    / {_fmt(contexte.get('bareme'))}</div>
    <div>Rang dans la classe : {escape(rang_txt)}</div>
    <div>Mention : {escape(str(contexte.get('mention', '') or '—'))}</div>
    <div>Présences : {int(presences.get('present', 0))} présent(s),
    {int(presences.get('absent', 0))} absence(s),
    {int(presences.get('retard', 0))} retard(s),
    {int(presences.get('excuse', 0))} excusée(s)</div>
  </div>
  <div class="appreciation">
    <div>Appréciation générale :</div>
    <div class="cadre">{escape(str(contexte.get('appreciation_generale', '') or ''))}</div>
  </div>
  <div class="signature">Enseignant principal :
  {escape(str(contexte.get('enseignant_principal', '') or '—'))}</div>
</body></html>"""


def render_bulletin_pdf(contexte):
    """Octets PDF du bulletin — moteur PARTAGÉ ``core.pdf.render_pdf``."""
    return render_pdf(html=render_bulletin_html(contexte))
