"""ADSENG23 — Identité de lancement : nommage + UTM en UNE fonction.

``generate_launch_identity()`` est la SOURCE UNIQUE qui nomme les objets Meta
(campagne / ad set / ad) ET fabrique les paramètres UTM au moment de proposer
un lancement (dd-treasury §c). Le nommage est PARSABLE : le parseur inverse
(``parse_campaign_name`` / ``parse_adset_name`` / ``parse_ad_name``) sert
l'attribution — « quelle cohorte a gagné » se répond en lisant les noms, sans
table de jointure.

Convention ``utm_content = 'ad-<ad_id>'`` (choisie par P0/ADSENG1, formalisée
ici) : ``attribution._resolve_ad_id`` la lit (tier 1b) pour retrouver l'ad
exacte. ``build_utm_content`` / ``parse_utm_content`` sont l'aller-retour.

Gouvernance UTM : ``utm_source='meta'`` / ``utm_medium='cpc'`` (docs/utm-
governance.md Règles 1-2, déjà présentes) ; casing lowercase snake_case ASCII
(Règle 0). La Règle 5 (ajoutée dans le même commit) rend ces valeurs
autoritatives — jamais tapées à la main pour une campagne gérée par le moteur.
"""
from __future__ import annotations

import datetime
import unicodedata

CAMPAIGN_PREFIX = 'TQ'
UTM_SOURCE = 'meta'      # docs/utm-governance.md Règle 1
UTM_MEDIUM = 'cpc'       # docs/utm-governance.md Règle 2
UTM_CONTENT_AD_PREFIX = 'ad-'  # convention ADSENG1 (attribution tier 1b)

# Marchés (mappés 1:1 depuis ``Lead.TypeInstallation``) et objectifs Meta —
# vocabulaire FERMÉ : une valeur inconnue lève (anti-dérive, comme utm-
# governance Règle 1). ``industriel`` + ``commercial`` fusionnent en ``indcom``.
MARKETS = frozenset({'resid', 'indcom', 'agri'})
OBJECTIVES = frozenset({'ctwa', 'leadform', 'traffic'})
MARKET_FROM_TYPE_INSTALLATION = {
    'residentiel': 'resid',
    'commercial': 'indcom',
    'industriel': 'indcom',
    'agricole': 'agri',
}


def slug_token(value):
    """Casing utm-governance Règle 0 : minuscules, ASCII, [a-z0-9] uniquement
    (accents dépliés, tout le reste retiré — pas de séparateur ``-``/``_`` qui
    casserait la parsabilité par ``-``). Lève ``ValueError`` si vide après
    nettoyage (un composant de nom ne peut pas être vide)."""
    if value is None:
        raise ValueError("Composant d'identité vide.")
    text = unicodedata.normalize('NFKD', str(value))
    text = text.encode('ascii', 'ignore').decode('ascii').lower()
    cleaned = ''.join(c for c in text if c.isalnum())
    if not cleaned:
        raise ValueError(f"Composant d'identité vide après nettoyage : {value!r}")
    return cleaned


def market_for_type_installation(type_installation):
    """``Lead.TypeInstallation`` → code marché (``resid``/``indcom``/``agri``).
    Valeur inconnue → ``ValueError``."""
    key = str(type_installation or '').strip().lower()
    market = MARKET_FROM_TYPE_INSTALLATION.get(key)
    if market is None:
        raise ValueError(
            f"Type d'installation inconnu pour le marché : {type_installation!r}")
    return market


def build_utm_content(ad_id):
    """Convention ``ad-<ad_id>`` (ADSENG1). ``ad_id`` vide → None."""
    if not ad_id:
        return None
    return f'{UTM_CONTENT_AD_PREFIX}{ad_id}'


def parse_utm_content(utm_content):
    """Inverse de ``build_utm_content`` : ``'ad-123'`` → ``'123'`` ; toute autre
    forme (ou vide) → None (l'attribution retombe alors sur le fuzzy nom)."""
    text = str(utm_content or '')
    if text.startswith(UTM_CONTENT_AD_PREFIX):
        return text[len(UTM_CONTENT_AD_PREFIX):] or None
    return None


def build_utm(market, objective, city, variant, *, ad_id=None):
    """Paramètres UTM d'un lancement (casing Règle 0). ``utm_content`` est None
    tant qu'aucun ``ad_id`` n'est fourni (rempli par ad à la création)."""
    return {
        'utm_source': UTM_SOURCE,
        'utm_medium': UTM_MEDIUM,
        'utm_campaign': f'{market}_{objective}_{city}_{variant}'.lower(),
        'utm_content': build_utm_content(ad_id),
    }


def generate_launch_identity(*, market, objective, city, launch_date, variant,
                             company=None):
    """UNE fonction = nommage (campagne/adset/ad, PARSABLE) + UTM builder.

    Renvoie un dict : ``campaign_name`` (``TQ-YYYYMMDD-market-objective-city-
    variant``), gabarits ``adset_name_tmpl`` / ``ad_name_tmpl`` (``{n:02d}``
    rempli à la création), les composants sluggés (pour l'aller-retour), et les
    paramètres UTM. ``market`` / ``objective`` sont validés (vocabulaire fermé).

    ``company`` est accepté pour le futur white-label (le préfixe ``TQ-``
    deviendrait configurable par tenant via ``core.TenantTheme``, dd-treasury
    §d) — non utilisé aujourd'hui, aucun cas particulier."""
    m = str(market or '').strip().lower()
    obj = str(objective or '').strip().lower()
    if m not in MARKETS:
        raise ValueError(
            f"Marché inconnu : {market!r} (attendus : {sorted(MARKETS)}).")
    if obj not in OBJECTIVES:
        raise ValueError(
            f"Objectif inconnu : {objective!r} (attendus : "
            f"{sorted(OBJECTIVES)}).")
    city_slug = slug_token(city)
    variant_slug = slug_token(variant)
    date_code = launch_date.strftime('%Y%m%d')
    campaign_name = (
        f'{CAMPAIGN_PREFIX}-{date_code}-{m}-{obj}-{city_slug}-{variant_slug}')
    utm = build_utm(m, obj, city_slug, variant_slug)
    return {
        'campaign_name': campaign_name,
        'adset_name_tmpl': '{campaign_name}-AS-{n:02d}',
        'ad_name_tmpl': '{campaign_name}-AS-{n:02d}-AD-{creative_asset_id}',
        'market': m,
        'objective': obj,
        'city': city_slug,
        'variant': variant_slug,
        'launch_date': launch_date,
        **utm,
    }


# ── Parseur inverse (sert l'attribution) ──────────────────────────────────
def parse_campaign_name(name):
    """``TQ-YYYYMMDD-market-objective-city-variant`` → dict. Lève ``ValueError``
    sur préfixe inattendu, mauvais nombre de segments, ou date illisible."""
    parts = str(name or '').split('-')
    if len(parts) != 6:
        raise ValueError(f"Nom de campagne non parsable : {name!r}")
    prefix, date_code, market, objective, city, variant = parts
    if prefix != CAMPAIGN_PREFIX:
        raise ValueError(
            f"Préfixe inattendu {prefix!r} (attendu {CAMPAIGN_PREFIX!r}).")
    launch_date = datetime.datetime.strptime(date_code, '%Y%m%d').date()
    return {
        'prefix': prefix, 'launch_date': launch_date, 'market': market,
        'objective': objective, 'city': city, 'variant': variant,
    }


def parse_adset_name(name):
    """``<campaign_name>-AS-NN`` → ``{campaign_name, n}``."""
    text = str(name or '')
    if '-AS-' not in text:
        raise ValueError(f"Nom d'ad set non parsable : {name!r}")
    campaign_name, suffix = text.rsplit('-AS-', 1)
    return {'campaign_name': campaign_name, 'n': int(suffix)}


def parse_ad_name(name):
    """``<campaign_name>-AS-NN-AD-<creative_asset_id>`` →
    ``{campaign_name, n, creative_asset_id}``."""
    text = str(name or '')
    if '-AD-' not in text:
        raise ValueError(f"Nom d'ad non parsable : {name!r}")
    adset_part, creative_id = text.rsplit('-AD-', 1)
    adset = parse_adset_name(adset_part)
    return {
        'campaign_name': adset['campaign_name'], 'n': adset['n'],
        'creative_asset_id': creative_id,
    }


def next_adset_index(company, campaign_name):
    """Prochain indice d'ad set = plus-haut-utilisé + 1 pour CE ``campaign_name``
    (jamais ``count()+1`` — un miroir supprimé ne doit pas provoquer de
    collision, même leçon que ``ventes/utils/references.py``). Interroge
    ``AdSetMirror`` (même app)."""
    from .models import AdSetMirror
    prefix = f'{campaign_name}-AS-'
    highest = 0
    names = (AdSetMirror.objects
             .filter(company=company, name__startswith=prefix)
             .values_list('name', flat=True))
    for name in names:
        try:
            highest = max(highest, parse_adset_name(name)['n'])
        except (ValueError, KeyError):
            continue
    return highest + 1
