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


# ── NTCON9 — DGD (Décompte Général et Définitif) ────────────────────────────

def render_dgd_pdf(dgd):
    """PDF interne (WeasyPrint) du DGD — document contractuel de clôture de
    chantier, jamais le moteur devis premium (hors rule #4 — document
    interne/MOE, pas un devis client)."""
    lignes = [
        ('Montant marché initial HT', dgd.montant_marche_initial_ht),
        ('Total avenants approuvés HT', dgd.total_avenants_ht),
        ('Total situations facturées HT', dgd.total_situations_facturees_ht),
        ('Retenue de garantie libérée', dgd.retenue_garantie_montant or 0),
        ('Solde dû HT', dgd.solde_du_ht),
    ]
    corps = ''.join(
        f'<tr><td>{_esc(libelle)}</td><td>{_esc(montant)}</td></tr>'
        for libelle, montant in lignes)

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
  <h1>Décompte Général et Définitif — {_esc(dgd.reference)}</h1>
  <p>Chantier : {_esc(dgd.chantier)}</p>
  <p>Statut : {_esc(dgd.get_statut_display())}</p>
  <table>
    <thead><tr><th>Poste</th><th>Montant</th></tr></thead>
    <tbody>{corps}</tbody>
  </table>
</body>
</html>'''
    return render_pdf(html=html)
