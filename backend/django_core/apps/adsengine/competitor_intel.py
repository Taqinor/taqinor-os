"""PUB70 — Veille concurrentielle publicitaire (périmètre HONNÊTE, zéro scraping).

ÉTAPE 1 (finding documenté) : l'API officielle Meta Ad Library
(``ads_archive``) ne renvoie QUE les publicités relatives à la politique, aux
élections ou aux enjeux sociaux — les pubs COMMERCIALES (dont le solaire
marocain) n'y sont PAS exposées, et la couverture pays de l'API politique est
elle-même limitée. Conclusion : aucune couverture API pour les pubs commerciales
MA/MENA (:func:`ad_library_api_covers_commercial` → toujours ``False``).

Conséquence (règle #5 — jamais de scraping) : la veille est MANUELLE et
OUTILLÉE. On suit des Pages concurrentes (``CompetitorPage``), on ouvre l'Ad
Library WEB via un lien profond, et l'humain SAISIT les hooks/angles observés
(``CompetitorAdObservation``) « pour inspiration », jamais copiés verbatim. Ce
module ne fait AUCUN appel réseau : il calcule une timeline de cadence et
transforme des observations en matière de brief. Tout passage à une collecte
AUTOMATISÉE est GATED : décision fondateur + dossier ``tos_risk/`` (non fourni
ici).
"""
from __future__ import annotations

import datetime

# Le finding, exposé comme donnée exploitable par l'écran (jamais un chiffre
# inventé : c'est une caractéristique documentée de l'API Meta).
AD_LIBRARY_API_FINDING = {
    'covers_commercial': False,
    'reason_fr': (
        "L'API Ad Library de Meta ne renvoie que les publicités politiques / "
        "enjeux sociaux ; les pubs commerciales (solaire MA/MENA) n'y sont pas "
        "exposées. Veille manuelle outillée (règle #5 : aucun scraping)."),
    'automation_status': 'GATED',  # décision fondateur + dossier tos_risk/
}


def ad_library_api_covers_commercial(country='MA'):
    """PUB70 — ÉTAPE 1 : l'API Ad Library couvre-t-elle les pubs COMMERCIALES du
    pays ? Toujours ``False`` (l'API ne sert que politique/enjeux sociaux) — le
    ``country`` est accepté pour une signature stable mais ne change rien."""
    return False


def cadence_timeline(company, *, weeks=8, today=None):
    """PUB70 — Cadence d'observation PAR CONCURRENT sur ``weeks`` semaines
    glissantes (nombre d'observations manuelles saisies par semaine ISO).

    Lecture seule, company-scopé. Renvoie
    ``[{competitor_id, competitor, total, par_semaine: {'YYYY-Www': n}}]`` trié
    par volume décroissant. Ne compte QUE des saisies humaines (aucune collecte
    automatique). Une semaine sans observation est simplement absente (jamais un
    zéro fabriqué)."""
    from .models import CompetitorAdObservation, CompetitorPage

    today = today or datetime.date.today()
    horizon = today - datetime.timedelta(weeks=weeks)
    pages = {p.id: p for p in CompetitorPage.objects.filter(company=company)}
    rows = {}
    obs = (CompetitorAdObservation.objects
           .filter(company=company, observed_at__gte=horizon,
                   observed_at__lte=today))
    for o in obs:
        page = pages.get(o.competitor_page_id)
        if page is None:
            continue
        entry = rows.setdefault(o.competitor_page_id, {
            'competitor_id': o.competitor_page_id,
            'competitor': page.name, 'total': 0, 'par_semaine': {}})
        iso = o.observed_at.isocalendar()
        wk = f'{iso[0]:04d}-W{iso[1]:02d}'
        entry['par_semaine'][wk] = entry['par_semaine'].get(wk, 0) + 1
        entry['total'] += 1
    return sorted(rows.values(), key=lambda r: r['total'], reverse=True)


def observations_as_brief_material(company, *, competitor_id=None, limit=20):
    """PUB70 — Transforme des observations manuelles en MATIÈRE de brief
    (« inspiration »). Renvoie une liste de dicts
    ``{hook_text, angle, format, competitor, observed_at, source_url}`` — jamais
    un contenu copié verbatim ni un chiffre : ce sont des repères d'angle saisis
    par l'humain, à re-formuler dans un brief. Company-scopé."""
    from .models import CompetitorAdObservation

    qs = CompetitorAdObservation.objects.filter(
        company=company).select_related('competitor_page')
    if competitor_id is not None:
        qs = qs.filter(competitor_page_id=competitor_id)
    rows = []
    for o in qs[:limit]:
        if not (o.hook_text or o.angle):
            continue  # une observation vide n'inspire rien
        rows.append({
            'hook_text': o.hook_text, 'angle': o.angle, 'format': o.format,
            'competitor': o.competitor_page.name,
            'observed_at': o.observed_at.isoformat(),
            'source_url': o.source_url,
        })
    return rows
