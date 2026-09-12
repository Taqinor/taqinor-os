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


# ── NTCON18 — Photo-rapport hebdomadaire (avancement photo) ────────────────

def render_rapport_photo_pdf(chantier, du, au, photos):
    """PDF « avancement photo » d'une période (NTCON18).

    ``photos`` est une liste de dicts ``{source, date, phase, filename,
    data_uri}`` déjà constituée par ``services.collecter_photos_periode``
    (les octets sont embarqués en ``data:`` URI — WeasyPrint ne joint jamais
    MinIO lui-même). Document destiné au CLIENT/MOE : uniquement des photos
    datées, JAMAIS un coût interne, jamais un prix d'achat (CLAUDE.md).
    """
    cartes = []
    for photo in photos:
        visuel = (
            f'<img src="{photo["data_uri"]}" alt="{_esc(photo["filename"])}" />'
            if photo.get('data_uri')
            else '<div class="manquant">Aperçu indisponible</div>')
        cartes.append(f'''
      <div class="photo">
        {visuel}
        <div class="legende">
          {_esc(photo.get('date') or '')} · {_esc(photo.get('source') or '')}
          {(' · ' + _esc(photo['phase'])) if photo.get('phase') else ''}
        </div>
      </div>''')
    corps = ''.join(cartes) or (
        '<p>Aucune photo sur la période.</p>')

    html = f'''<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><style>
  body {{ font-family: sans-serif; font-size: 11px; }}
  h1 {{ font-size: 16px; }}
  .photo {{ display: inline-block; width: 46%; margin: 0 1% 12px; vertical-align: top; }}
  .photo img {{ width: 100%; height: auto; border: 1px solid #ccc; }}
  .legende {{ font-size: 9px; color: #444; margin-top: 2px; }}
  .manquant {{ border: 1px dashed #ccc; padding: 18px; text-align: center; color: #888; }}
</style></head>
<body>
  <h1>Avancement photo — {_esc(chantier)}</h1>
  <p>Période du {_esc(du)} au {_esc(au)}</p>
  {corps}
</body>
</html>'''
    return render_pdf(html=html)


# ── NTCON22 — Rapport hebdomadaire d'avancement (INTERNE/MOE) ──────────────

def render_rapport_avancement_pdf(chantier, donnees):
    """PDF INTERNE d'avancement de chantier sur une période (NTCON22).

    ``donnees`` vient de ``selectors.rapport_avancement``. Document de suivi
    interne/MOE : JAMAIS un devis client, jamais exposé via ``/proposal``
    (règle #4), AUCUN prix d'achat ni coût — uniquement de l'avancement, des
    réserves, des RFI, des effectifs et des points d'arrêt QHSE.
    """
    lots = ''.join(
        f'''<tr>
            <td>{_esc(lot['nom'])}</td>
            <td>{_esc(lot['statut'])}</td>
            <td>{_esc(lot['avancement_pct'])} %</td>
            <td>{_esc(lot['date_fin_prevue'] or '—')}</td>
            <td>{_esc(lot['date_fin_reelle'] or '—')}</td>
            <td>{_esc(lot['jours_retard'])}</td>
          </tr>''' for lot in donnees['lots']
    ) or '<tr><td colspan="6">Aucun lot défini.</td></tr>'

    rfis = ''.join(
        f'''<tr>
            <td>{_esc(rfi['numero'])}</td>
            <td>{_esc(rfi['question'])}</td>
            <td>{_esc(rfi['date_limite_reponse'] or '—')}</td>
            <td>{'En retard' if rfi['en_retard'] else 'Dans les temps'}</td>
          </tr>''' for rfi in donnees['rfi_en_cours']
    ) or '<tr><td colspan="4">Aucun RFI en cours.</td></tr>'

    points = ''.join(
        f'<li>{_esc(point.get("plan_nom", ""))} — '
        f'{_esc(point.get("libelle") or point.get("nom") or "point d\'arrêt")}'
        '</li>'
        for point in donnees['qhse_points_arret_bloquants']
    ) or '<li>Aucun point d\'arrêt bloquant.</li>'

    reserves = donnees['reserves']
    effectif = donnees['effectif_moyen']

    html = f'''<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><style>
  body {{ font-family: sans-serif; font-size: 11px; }}
  h1 {{ font-size: 16px; }}
  h2 {{ font-size: 13px; margin-top: 14px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; text-align: left; }}
  th {{ background: #f2f2f2; }}
</style></head>
<body>
  <h1>Rapport d'avancement — {_esc(chantier)}</h1>
  <p>Période du {_esc(donnees['du'])} au {_esc(donnees['au'])}
     — document interne / MOE.</p>

  <h2>Avancement des lots</h2>
  <table>
    <thead><tr>
      <th>Lot</th><th>Statut</th><th>Avancement</th>
      <th>Fin prévue</th><th>Fin réelle</th><th>Retard (j)</th>
    </tr></thead>
    <tbody>{lots}</tbody>
  </table>

  <h2>Réserves</h2>
  <p>
    Créées sur la période : {_esc(reserves['creees_periode'])} ·
    Levées : {_esc(reserves['levees_periode'])} ·
    Encore ouvertes : {_esc(reserves['ouvertes'])}
    (dont bloquantes : {_esc(reserves['bloquantes_ouvertes'])})
  </p>

  <h2>RFI en cours</h2>
  <table>
    <thead><tr>
      <th>N°</th><th>Question</th><th>Échéance</th><th>État</th>
    </tr></thead>
    <tbody>{rfis}</tbody>
  </table>

  <h2>Effectifs moyens</h2>
  <p>
    {_esc(effectif['jours_renseignes'])} jour(s) de journal renseigné(s) ·
    Interne : {_esc(effectif['moyenne_interne'])} ·
    Sous-traitance : {_esc(effectif['moyenne_sous_traitant'])}
  </p>

  <h2>Points d'arrêt QHSE bloquants</h2>
  <ul>{points}</ul>
</body>
</html>'''
    return render_pdf(html=html)
