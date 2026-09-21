"""NTEDU18 — Certificat de scolarité PDF, à la demande.

Même moteur WeasyPrint sobre que ``apps.compta.pdf_certificat_enquete`` —
PAS le quote engine premium (règle #4 CLAUDE.md non concernée, ce n'est ni un
devis ni une facture). Contenu minimal : nom élève, classe, année scolaire,
numéro de certificat (attribué côté serveur via ``core.numbering`` par
``services.generer_certificat_scolarite``, jamais ici). ``core.pdf.
render_pdf`` porte la plomberie WeasyPrint partagée (import paresseux).
"""
from html import escape

from core.pdf import render_pdf

_STYLE = """
  body { font-family: sans-serif; margin: 60px; text-align: center; }
  .cadre { border: 3px solid #1e293b; padding: 50px 40px; }
  h1 { font-size: 24px; margin-bottom: 24px; }
  .champ { font-size: 14px; margin: 10px 0; text-align: left; }
  .numero { margin-top: 40px; font-size: 12px; color: #555; }
"""


def render_certificat_scolarite_html(
        *, nom_eleve, classe_nom, annee_scolaire_libelle, numero,
        date_generation, company_nom=''):
    """HTML du certificat de scolarité (NTEDU18)."""
    date_txt = date_generation.strftime('%d/%m/%Y')
    entete = (
        f"<p class=\"champ\">{escape(company_nom)}</p>" if company_nom else '')
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  <div class="cadre">
    {entete}
    <h1>Certificat de scolarité</h1>
    <p class="champ">Nom et prénom : <strong>{escape(nom_eleve)}</strong></p>
    <p class="champ">Classe : {escape(classe_nom)}</p>
    <p class="champ">Année scolaire : {escape(annee_scolaire_libelle)}</p>
    <p class="champ">Ce document atteste que l'élève est régulièrement
    inscrit(e) dans notre établissement au titre de l'année scolaire
    ci-dessus.</p>
    <p class="numero">Certificat n° {escape(numero)} — délivré le
    {escape(date_txt)}.</p>
  </div>
</body></html>"""


def render_certificat_scolarite_pdf(
        *, nom_eleve, classe_nom, annee_scolaire_libelle, numero,
        date_generation, company_nom=''):
    return render_pdf(html=render_certificat_scolarite_html(
        nom_eleve=nom_eleve, classe_nom=classe_nom,
        annee_scolaire_libelle=annee_scolaire_libelle, numero=numero,
        date_generation=date_generation, company_nom=company_nom))
