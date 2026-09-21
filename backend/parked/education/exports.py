"""NTEDU37 — export de la liste d'une classe (PDF/Excel), usage administratif
(rentrée, sorties scolaires). Contenu : élève + contacts parents. openpyxl
(pré-approuvé, même patron que ``apps.ventes.exports``) pour le .xlsx ;
``core.pdf.render_pdf`` (WeasyPrint partagé, PAS le quote engine — règle #4
non concernée, ce n'est ni un devis ni une facture) pour le .pdf. Lecture
seule, bornée à la société via ``classe.company`` (jamais un id lu du corps
de requête)."""
from html import escape

_HEADERS = [
    'Nom', 'Prénom', 'N° dossier', 'Date de naissance',
    'Parent 1 — nom', 'Parent 1 — téléphone', 'Parent 1 — email',
    'Parent 2 — nom', 'Parent 2 — téléphone', 'Parent 2 — email',
]


def _rows(classe):
    eleves = (classe.eleves
              .select_related('famille')
              .order_by('nom', 'prenom'))
    rows = []
    for e in eleves:
        f = e.famille
        rows.append([
            e.nom, e.prenom, e.numero_dossier or '',
            e.date_naissance.isoformat() if e.date_naissance else '',
            f.parent1_nom, f.parent1_telephone, f.parent1_email,
            f.parent2_nom, f.parent2_telephone, f.parent2_email,
        ])
    return rows


def export_classe_xlsx_bytes(classe):
    """Construit le classeur .xlsx (une feuille, une ligne par élève) et
    renvoie ses octets."""
    import io

    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = 'Liste de classe'
    bold = Font(bold=True)
    ws.append(_HEADERS)
    for c in ws[1]:
        c.font = bold
    for row in _rows(classe):
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_classe_pdf_bytes(classe):
    """Construit le PDF (tableau simple) de la liste de classe et renvoie
    ses octets."""
    from core.pdf import render_pdf

    lignes_html = ''.join(
        '<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>'
        for row in _rows(classe))
    entetes_html = ''.join(f'<th>{escape(h)}</th>' for h in _HEADERS)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; margin: 30px; }}
  h1 {{ font-size: 18px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
  th, td {{ border: 1px solid #999; padding: 4px 6px; text-align: left; }}
  th {{ background: #eee; }}
</style></head><body>
  <h1>Liste de classe — {escape(str(classe))}</h1>
  <table>
    <thead><tr>{entetes_html}</tr></thead>
    <tbody>{lignes_html}</tbody>
  </table>
</body></html>"""
    return render_pdf(html=html)
