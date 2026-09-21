"""Rapport ESG PDF GRI-lite (NTESG4) — JAMAIS ``/proposal`` (règle #4,
CLAUDE.md : ce chemin ne rend QUE des devis client), aucune donnée
commerciale/prix.

``rapport_esg_sections`` construit la liste de sections (indépendante du
rendu HTML/PDF, testable sans dépendance WeasyPrint) : une section OMISE
n'apparaît PAS dans la liste — jamais de placeholder « N/A »/« 0 » pour un
pilier ou une source sans donnée (règle checked-facts-only).
``generer_rapport_esg_pdf`` rend ensuite ces sections en PDF via le service
PARTAGÉ ``core.pdf.render_pdf`` (ARC11 — jamais un appel WeasyPrint direct).
"""
import html as _html

BANNIERE = 'Rapport interne — méthodologie propriétaire, non audité'
NOTE_BILAN_CARBONE = (
    'Facteurs d\'émission génériques, non vérifiés par un tiers — à faire '
    "valider par un organisme accrédité avant toute communication "
    'réglementaire.')


def _esc(value):
    if value is None:
        return ''
    return _html.escape(str(value))


def rapport_esg_sections(periode_esg):
    """Sections du rapport ESG d'une période, DÉJÀ filtrées checked-facts-only
    (NTESG4). Chaque section correspond à une page logique du PDF.

    Renvoie une liste ordonnée de dicts ``{'type': ..., ...}`` :
    ``garde`` (toujours présente), ``indicateurs`` (piliers E/S/G non
    vides), ``bilan_carbone`` (si disponible), ``social_environnement``
    (HSE/carburant/effectifs, si au moins une sous-source disponible),
    ``objectifs`` (trajectoires ESG actives, si au moins un objectif
    existe pour la société)."""
    from .selectors import donnees_effectives_periode, trajectoire_vs_realise

    donnees = donnees_effectives_periode(periode_esg)
    sources = donnees.get('sources', {})

    sections = [{
        'type': 'garde',
        'societe': getattr(periode_esg.company, 'nom', ''),
        'libelle': periode_esg.libelle,
        'date_debut': periode_esg.date_debut,
        'date_fin': periode_esg.date_fin,
        'statut': periode_esg.statut,
    }]

    indic = sources.get('indicateurs_esg') or {}
    if indic.get('disponible'):
        piliers_non_vides = {
            k: v for k, v in (indic.get('piliers') or {}).items()
            if v.get('nb', 0) > 0
        }
        if piliers_non_vides:
            sections.append({
                'type': 'indicateurs', 'piliers': piliers_non_vides,
            })

    bilan = sources.get('bilan_carbone') or {}
    if bilan.get('disponible'):
        sections.append({'type': 'bilan_carbone', 'data': bilan})

    social_env = {}
    hse = sources.get('social_hse') or {}
    if hse.get('disponible'):
        social_env['hse'] = hse
    carburant = sources.get('carburant_flotte') or {}
    if carburant.get('disponible'):
        social_env['carburant'] = carburant
    effectifs = sources.get('effectifs') or {}
    if effectifs.get('disponible'):
        social_env['effectifs'] = effectifs
    if social_env:
        sections.append({'type': 'social_environnement', **social_env})

    from .models import ObjectifESGTrajectoire

    objectifs_qs = ObjectifESGTrajectoire.objects.filter(
        company=periode_esg.company, actif=True)
    objectifs = [
        {'objectif': o, 'trajectoire': trajectoire_vs_realise(o)}
        for o in objectifs_qs
    ]
    if objectifs:
        sections.append({'type': 'objectifs', 'objectifs': objectifs})

    return sections


def _render_garde(section):
    return f"""
    <section class="page">
      <h1>Rapport ESG — {_esc(section['societe'])}</h1>
      <p class="sous-titre">{_esc(section['libelle'])}</p>
      <p>Période : {_esc(section['date_debut'])} — {_esc(section['date_fin'])}</p>
      <p>Statut : {_esc(section['statut'])}</p>
    </section>"""


def _render_indicateurs(section):
    blocs = []
    for pilier, bloc in section['piliers'].items():
        lignes = ''.join(
            f"<tr><td>{_esc(ligne.get('code'))}</td>"
            f"<td>{_esc(ligne.get('libelle'))}</td>"
            f"<td>{_esc(ligne.get('valeur'))} {_esc(ligne.get('unite'))}</td>"
            f"<td>{_esc(ligne.get('cible'))}</td></tr>"
            for ligne in bloc.get('lignes', [])
        )
        blocs.append(f"""
          <h3>{_esc(pilier)}</h3>
          <table>
            <thead><tr><th>Code</th><th>Libellé</th>
              <th>Valeur</th><th>Cible</th></tr></thead>
            <tbody>{lignes}</tbody>
          </table>""")
    return f"""
    <section class="page">
      <h2>Indicateurs ESG par pilier</h2>
      {''.join(blocs)}
    </section>"""


def _render_bilan_carbone(section):
    data = section['data']
    return f"""
    <section class="page">
      <h2>Bilan carbone</h2>
      <p class="note">{_esc(NOTE_BILAN_CARBONE)}</p>
      <pre>{_esc(data)}</pre>
    </section>"""


def _render_social_environnement(section):
    blocs = []
    hse = section.get('hse')
    if hse:
        blocs.append(f"""
          <h3>Hygiène-Sécurité (HSE)</h3>
          <ul>
            <li>Taux de fréquence : {_esc(hse.get('taux_frequence'))}</li>
            <li>Taux de gravité : {_esc(hse.get('taux_gravite'))}</li>
            <li>Accidents du travail : {_esc(hse.get('accidents_total'))}</li>
            <li>Presqu'accidents : {_esc(hse.get('presqu_accidents_total'))}</li>
          </ul>""")
    carburant = section.get('carburant')
    if carburant:
        blocs.append(f"""
          <h3>Carburant flotte</h3>
          <ul>
            <li>Gasoil : {_esc(carburant.get('gasoil_litres'))} L</li>
            <li>Essence : {_esc(carburant.get('essence_litres'))} L</li>
            <li>Électrique : {_esc(carburant.get('electrique_kwh'))} kWh</li>
          </ul>""")
    effectifs = section.get('effectifs')
    if effectifs:
        blocs.append(f"""
          <h3>Effectifs</h3>
          <p>Effectif actif : {_esc(effectifs.get('effectif_actif'))}</p>""")
    return f"""
    <section class="page">
      <h2>Social &amp; environnement (agrégation cross-app)</h2>
      {''.join(blocs)}
    </section>"""


def _render_objectifs(section):
    blocs = []
    for entry in section['objectifs']:
        objectif = entry['objectif']
        lignes = ''.join(
            f"<tr><td>{_esc(p['annee'])}</td>"
            f"<td>{_esc(p['theorique'])}</td>"
            f"<td>{_esc(p['reel']) if p['reel'] is not None else '—'}</td>"
            f"<td>{_esc(p['ecart_pct']) if p['ecart_pct'] is not None else '—'}</td>"
            f"</tr>"
            for p in entry['trajectoire']
        )
        blocs.append(f"""
          <h3>{_esc(objectif.indicateur_code)} — {_esc(objectif.libelle)}</h3>
          <table>
            <thead><tr><th>Année</th><th>Trajectoire théorique</th>
              <th>Réel</th><th>Écart %</th></tr></thead>
            <tbody>{lignes}</tbody>
          </table>""")
    return f"""
    <section class="page">
      <h2>Objectifs vs réalisé</h2>
      {''.join(blocs)}
    </section>"""


_RENDERERS = {
    'garde': _render_garde,
    'indicateurs': _render_indicateurs,
    'bilan_carbone': _render_bilan_carbone,
    'social_environnement': _render_social_environnement,
    'objectifs': _render_objectifs,
}


def _build_html(sections):
    body = ''.join(_RENDERERS[s['type']](s) for s in sections)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: sans-serif; font-size: 11px; color: #222; }}
  .page {{ page-break-before: always; padding: 24px 0; }}
  .page:first-child {{ page-break-before: auto; }}
  h1 {{ font-size: 20px; }}
  h2 {{ font-size: 16px; border-bottom: 1px solid #ccc; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 4px 6px; text-align: left; }}
  .note {{ font-style: italic; color: #555; }}
  .banniere {{
    position: fixed; bottom: 0; left: 0; right: 0;
    font-size: 8px; color: #999; text-align: center;
  }}
</style>
</head>
<body>
  <div class="banniere">{_esc(BANNIERE)}</div>
  {body}
</body>
</html>"""


def generer_rapport_esg_pdf(periode_esg):
    """Rend le rapport ESG GRI-lite d'une période en PDF (NTESG4).

    Utilise ``donnees_effectives_periode`` (snapshot gelé si figée, aperçu
    live sinon) — jamais un recalcul d'une période déjà figée. Chaque
    section absente/indisponible est ENTIÈREMENT OMISE du document (jamais
    de placeholder trompeur)."""
    from core.pdf import render_pdf

    sections = rapport_esg_sections(periode_esg)
    html = _build_html(sections)
    return render_pdf(html=html)
