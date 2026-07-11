"""ZMKT10 — Certificat PDF de réussite d'une enquête « certification ».

Même moteur WeasyPrint sobre que ``pdf_notes_frais.py``/``pdf_ras.py`` — PAS
le quote engine premium (règle #4 CLAUDE.md non concernée, ce n'est pas un
devis). Contenu minimal : nom du répondant, titre de l'enquête, score, date.
Aucune donnée interne (prix_achat/marge) — sans objet ici de toute façon.

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()`` + import
paresseux) est déléguée au service partagé ``core.pdf.render_pdf`` ; le
GABARIT HTML ci-dessous reste STRICTEMENT identique, donc le rendu est
inchangé à l'octet près.
"""
from datetime import date
from html import escape

from core.pdf import render_pdf


def _html_to_pdf(html_string):
    """HTML → octets PDF via ``core.pdf.render_pdf`` (ARC12)."""
    return render_pdf(html=html_string)


_STYLE = """
  body { font-family: sans-serif; margin: 60px; text-align: center; }
  .cadre { border: 4px solid #2563EB; padding: 60px 40px; }
  h1 { font-size: 28px; color: #2563EB; margin-bottom: 8px; }
  .titre-enquete { font-size: 18px; margin: 24px 0; }
  .nom { font-size: 22px; font-weight: bold; margin: 16px 0; }
  .score { font-size: 16px; margin-top: 24px; }
  .date { margin-top: 40px; font-size: 12px; color: #555; }
"""


def render_certificat_html(*, nom_repondant, titre_enquete, score_pct, today=None):
    """HTML du certificat de réussite (ZMKT10)."""
    today = today or date.today()
    date_txt = today.strftime('%d/%m/%Y')
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  <div class="cadre">
    <h1>Certificat de réussite</h1>
    <p class="titre-enquete">{escape(titre_enquete)}</p>
    <p class="nom">{escape(nom_repondant)}</p>
    <p class="score">Score obtenu : {score_pct}%</p>
    <p class="date">Délivré le {escape(date_txt)}.</p>
  </div>
</body></html>"""


def render_certificat_pdf(*, nom_repondant, titre_enquete, score_pct, today=None):
    return _html_to_pdf(
        render_certificat_html(
            nom_repondant=nom_repondant, titre_enquete=titre_enquete,
            score_pct=score_pct, today=today))
