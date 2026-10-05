"""PUB70 — Veille concurrentielle publicitaire (périmètre HONNÊTE, zéro scraping).

ÉTAPE 1 (finding documenté, CORRIGÉ PAR PAYS le 03/10/2026 — VEIL10) : la
couverture de l'API officielle Meta Ad Library (``ads_archive``) DÉPEND DU PAYS
atteint par la publicité. Pour les 27 pays de l'Union européenne, les pubs
COMMERCIALES y sont servies (portée UE) ; pour le Royaume-Uni les sources de
Meta se contredisent (page d'accès « UK or EU », page de référence « politique
seulement hors UE ») → statut ``a_confirmer`` tant que la mesure VEIL41 n'a pas
tranché ; hors UE et Royaume-Uni (Maroc, États-Unis, Australie…), seules les
pubs politiques / enjeux sociaux sont servies. La table UNIQUE est
:data:`VEILLE_COUVERTURE` (source https://www.facebook.com/ads/library/api/ ,
lue le 03/10/2026) ; :func:`ad_library_api_covers_commercial` répond PAR PAYS.

La veille MANUELLE et OUTILLÉE reste inchangée (règle #5 — jamais de scraping) :
on suit des Pages concurrentes (``CompetitorPage``), on ouvre l'Ad Library WEB
via un lien profond, et l'humain SAISIT les hooks/angles observés
(``CompetitorAdObservation``) « pour inspiration », jamais copiés verbatim. Les
fonctions de ce module ne font AUCUN appel réseau : elles calculent une timeline
de cadence et transforment des observations en matière de brief. La lecture par
l'API officielle (pilote VEILLE, à la demande, plafonnée) vit dans
``ad_library_client.py`` / ``veille_decouverte.py`` ; toute collecte du site web
reste GATED (décision fondateur + dossier ``tos_risk/``).
"""
from __future__ import annotations

import datetime

# ── VEIL10 — Couverture de l'API Ad Library PAR PAYS (table UNIQUE) ─────────
# Source : https://www.facebook.com/ads/library/api/ (lue le 03/10/2026).
# Codes ISO-3166 alpha-2 : la Grèce est ``GR`` (jamais ``EL``, code Eurostat),
# le Royaume-Uni ``GB`` (jamais ``UK``). Toute modification passe par ICI.
COUVERTURE_SOURCE_URL = 'https://www.facebook.com/ads/library/api/'
COUVERTURE_LU_LE = '2026-10-03'

PAYS_UE = (
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
    'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK',
    'SI', 'ES', 'SE',
)

COUVERT, A_CONFIRMER, NON_COUVERT = 'couvert', 'a_confirmer', 'non_couvert'

MOTIF_COUVERT = (
    "Pays de l'Union européenne : les pubs commerciales y sont servies par "
    "ads_archive avec la portée UE.")
MOTIF_A_CONFIRMER = (
    "Sources contradictoires sur le Royaume-Uni : à mesurer avant toute "
    "promesse.")
MOTIF_NON_COUVERT = (
    "Hors Union européenne et Royaume-Uni : seules les pubs politiques sont "
    "servies.")

VEILLE_COUVERTURE = {code: COUVERT for code in PAYS_UE}
# GB : contradiction documentaire — basculé par VEIL41 après mesure réelle.
VEILLE_COUVERTURE['GB'] = A_CONFIRMER
# Exemples explicites hors périmètre (tout code absent vaut aussi non_couvert).
VEILLE_COUVERTURE.update({'MA': NON_COUVERT, 'US': NON_COUVERT,
                          'AU': NON_COUVERT})

# Codes NON ISO refusés (jamais normalisés en silence : l'erreur est dite).
CODES_REFUSES = {
    'UK': "« UK » n'est pas un code ISO : utiliser « GB » (Royaume-Uni).",
    'EL': "« EL » n'est pas un code ISO : utiliser « GR » (Grèce).",
}

_MOTIFS = {
    COUVERT: MOTIF_COUVERT,
    A_CONFIRMER: MOTIF_A_CONFIRMER,
    NON_COUVERT: MOTIF_NON_COUVERT,
}


def normaliser_pays(code):
    """Code pays en majuscules, sans espaces. ``None``/``''`` → ``''``."""
    return str(code or '').strip().upper()


def statut_couverture(code):
    """Statut de couverture d'un pays : ``couvert`` | ``a_confirmer`` |
    ``non_couvert``. Insensible à la casse ; ``None``/``''``/inconnu/``UK``/
    ``EL`` → ``non_couvert`` (un code refusé n'est jamais couvert)."""
    norm = normaliser_pays(code)
    if not norm or norm in CODES_REFUSES:
        return NON_COUVERT
    return VEILLE_COUVERTURE.get(norm, NON_COUVERT)


def couverture_pays(code):
    """Ligne de couverture au format du contrat VEIL1 pour UN pays."""
    norm = normaliser_pays(code)
    statut = statut_couverture(norm)
    return {
        'pays': norm,
        'statut': statut,
        'motif_fr': CODES_REFUSES.get(norm) or _MOTIFS[statut],
        'source_url': COUVERTURE_SOURCE_URL,
        'lu_le': COUVERTURE_LU_LE,
    }


def couverture_liste():
    """Toutes les lignes de la table (UE triée, puis GB, puis exemples hors
    périmètre MA/US/AU) — ordre stable pour l'écran."""
    codes = sorted(PAYS_UE) + ['GB', 'MA', 'US', 'AU']
    return [couverture_pays(c) for c in codes]


# Le finding, exposé comme donnée par la route existante ``concurrents/veille/``
# (jamais un chiffre inventé). Il ne porte PLUS de booléen global : la
# couverture se lit PAR PAYS sur ``veille/couverture/`` (VEIL10).
AD_LIBRARY_API_FINDING = {
    'reason_fr': (
        "La couverture de l'API Ad Library de Meta dépend du pays : pubs "
        "commerciales servies pour les 27 pays de l'Union européenne, "
        "Royaume-Uni à confirmer, et seulement les pubs politiques ailleurs "
        "(dont le Maroc). Détail par pays dans la couverture de la veille ; "
        "la saisie manuelle ci-dessous reste disponible (règle #5 : aucun "
        "scraping)."),
    'couverture_url': '/api/django/adsengine/veille/couverture/',
    # Collecte du site web (hors API officielle) : toujours GATED.
    'automation_status': 'GATED',
}


def ad_library_api_covers_commercial(country=None):
    """VEIL10 — l'API Ad Library sert-elle les pubs COMMERCIALES du pays
    ``country`` ? Vrai SEULEMENT si le pays est ``couvert`` dans
    :data:`VEILLE_COUVERTURE` (insensible à la casse). ``None``/``''``/inconnu,
    ``GB`` (à confirmer) et les codes refusés ``UK``/``EL`` → ``False``."""
    return statut_couverture(country) == COUVERT


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
