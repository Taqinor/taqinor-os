"""Rendu PDF interne du vertical BTP/EPC (Groupe NTCON) — jamais un devis
client (règle #4) : la plomberie WeasyPrint est déléguée à ``core.pdf.
render_pdf`` (pattern ``qhse.pdf_terrain``), aucun prix d'achat."""
import html as _html

from core.pdf import render_pdf


def _esc(value):
    """Échappe le texte utilisateur injecté dans le HTML."""
    if value is None:
        return ''
    return _html.escape(str(value))


# ── NTCON6 — Journal de chantier (export hebdomadaire/mensuel) ─────────────

def render_journal_chantier_pdf(chantier, entries):
    """PDF interne du journal de chantier sur une période (NTCON6).

    ``entries`` est un itérable de ``JournalChantier`` (déjà filtré/scopé
    société+chantier+période par l'appelant). Aucun prix, aucune donnée
    financière — document de suivi de chantier interne/MOE.
    """
    lignes = []
    for j in entries:
        effectif_total = sum(
            (j.effectif_interne or {}).values()) if isinstance(
                j.effectif_interne, dict) else 0
        lignes.append(f'''
          <tr>
            <td>{_esc(j.date)}</td>
            <td>{_esc(j.get_meteo_display() if j.meteo else "")}</td>
            <td>{effectif_total}</td>
            <td>{_esc(j.materiel_present)}</td>
            <td>{_esc(j.evenements)}</td>
          </tr>''')
    corps = ''.join(lignes) or (
        '<tr><td colspan="5">Aucune entrée sur la période.</td></tr>')

    html = f'''<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><style>
  body {{ font-family: sans-serif; font-size: 11px; }}
  h1 {{ font-size: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; text-align: left; }}
  th {{ background: #f2f2f2; }}
</style></head>
<body>
  <h1>Journal de chantier — {_esc(chantier)}</h1>
  <table>
    <thead>
      <tr>
        <th>Date</th><th>Météo</th><th>Effectif interne</th>
        <th>Matériel présent</th><th>Événements</th>
      </tr>
    </thead>
    <tbody>{corps}</tbody>
  </table>
</body>
</html>'''
    return render_pdf(html=html)
