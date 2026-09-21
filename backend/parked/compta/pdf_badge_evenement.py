"""ZMKT19 — Badge PDF imprimable d'un inscrit à un événement (check-in).

Même moteur WeasyPrint sobre que ``pdf_notes_frais.py``/
``pdf_certificat_enquete.py`` — HORS ``/proposal`` (règle #4 CLAUDE.md non
concernée, ce n'est pas un devis). Aucune donnée interne (``prix_achat``)
— sans objet ici de toute façon.

ARC12 — la plomberie WeasyPrint (``HTML(string=...).write_pdf()`` + import
paresseux) est déléguée au service partagé ``core.pdf.render_pdf`` ; les
GABARITS HTML ci-dessous restent STRICTEMENT identiques, donc le rendu est
inchangé à l'octet près.
"""
from html import escape

from core.pdf import render_pdf


def _html_to_pdf(html_string):
    """HTML → octets PDF via ``core.pdf.render_pdf`` (ARC12)."""
    return render_pdf(html=html_string)


_STYLE = """
  @page { size: 90mm 130mm; margin: 6mm; }
  body { font-family: sans-serif; text-align: center; }
  .societe { font-size: 12px; color: #555; margin-bottom: 8px; }
  .nom { font-size: 20px; font-weight: bold; margin: 16px 0; }
  .evenement { font-size: 14px; color: #2563EB; margin-bottom: 16px; }
  .qr { margin-top: 16px; }
  .badge { page-break-after: always; }
"""


def _badge_html_fragment(*, nom_inscrit, nom_evenement, nom_societe, qr_svg):
    return f"""
  <div class="badge">
    <div class="societe">{escape(nom_societe)}</div>
    <div class="nom">{escape(nom_inscrit)}</div>
    <div class="evenement">{escape(nom_evenement)}</div>
    <div class="qr">{qr_svg}</div>
  </div>"""


def render_badge_html(*, nom_inscrit, nom_evenement, nom_societe='', qr_svg=''):
    """HTML d'UN badge (ZMKT19)."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  {_badge_html_fragment(
      nom_inscrit=nom_inscrit, nom_evenement=nom_evenement,
      nom_societe=nom_societe, qr_svg=qr_svg)}
</body></html>"""


def render_badges_html(inscrits):
    """HTML multi-pages (un badge par page, ZMKT19) — ``inscrits`` = liste de
    dicts ``{'nom_inscrit', 'nom_evenement', 'nom_societe', 'qr_svg'}``."""
    fragments = ''.join(
        _badge_html_fragment(**inscrit) for inscrit in inscrits)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{_STYLE}</style></head><body>
  {fragments}
</body></html>"""


def render_badge_pdf(*, nom_inscrit, nom_evenement, nom_societe='', qr_svg=''):
    return _html_to_pdf(render_badge_html(
        nom_inscrit=nom_inscrit, nom_evenement=nom_evenement,
        nom_societe=nom_societe, qr_svg=qr_svg))


def render_badges_pdf(inscrits):
    return _html_to_pdf(render_badges_html(inscrits))
