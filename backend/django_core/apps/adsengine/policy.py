"""ENG16 — Policy créative : check-list DÉTERMINISTE (l'humain confirme).

Principe : le système ne « lit » ni ne « juge » JAMAIS un créatif tout seul. Il
propose une check-list de règles (interdits / permis) et ENREGISTRE la
confirmation humaine règle par règle. ``policy_stamp.passed`` ne devient vrai que
si l'humain a confirmé CHAQUE règle interdite (le créatif ne les enfreint pas) —
c'est une trace d'un jugement HUMAIN, pas une évaluation automatique du contenu.

Défaut (seedé via ``seed_adsengine``) : jamais de faux chantiers / faux clients /
faux témoignages ni de chiffre non vérifié ; explainers animés / B-roll abstrait /
rendus produit sont explicitement permis. Chaque tenant peut définir sa propre
policy (``CreativePolicy`` par société).
"""
from __future__ import annotations

from django.utils import timezone

# Défauts (clés en anglais, libellés FR) — aucun littéral de marque codé en dur.
DEFAULT_FORBIDDEN = [
    {'key': 'no_fake_sites',
     'label': "Aucun faux chantier / installation mise en scène"},
    {'key': 'no_fake_clients',
     'label': "Aucun faux client ni acteur présenté comme client"},
    {'key': 'no_fake_testimonials', 'label': "Aucun faux témoignage"},
    {'key': 'no_unverified_numbers',
     'label': "Aucun chiffre non vérifié (économies, puissance, délais)"},
]
DEFAULT_ALLOWED = [
    {'key': 'animated_explainers', 'label': "Explainers animés"},
    {'key': 'abstract_broll', 'label': "B-roll abstrait"},
    {'key': 'product_renders', 'label': "Rendus produit (3D / studio)"},
]


def ensure_default_policy(company):
    """Idempotent : crée la ``CreativePolicy`` par défaut de ``company`` si
    absente (jamais d'écrasement). Renvoie ``(policy, created)``."""
    from .models import CreativePolicy

    return CreativePolicy.objects.get_or_create(
        company=company,
        defaults={
            'forbidden_rules': list(DEFAULT_FORBIDDEN),
            'allowed_rules': list(DEFAULT_ALLOWED),
        })


def _policy_rules(company):
    """Règles (interdits, permis) de la société — défauts si aucune policy."""
    from .models import CreativePolicy

    policy = CreativePolicy.objects.filter(company=company).first()
    if policy is None:
        return list(DEFAULT_FORBIDDEN), list(DEFAULT_ALLOWED)
    return list(policy.forbidden_rules or []), list(policy.allowed_rules or [])


def build_checklist(company):
    """Check-list à confirmer par l'humain (rendue par l'UI ENG27).

    Renvoie ``{'forbidden': [...], 'allowed': [...]}`` — les règles interdites
    doivent TOUTES être confirmées pour qu'un asset passe."""
    forbidden, allowed = _policy_rules(company)
    return {'forbidden': forbidden, 'allowed': allowed}


# PUB75 — Messages FR par raison de blocage consentement (CNDP loi 09-08).
CONSENT_BLOCK_LABELS = {
    'manquant': "Consentement client manquant (CNDP) : un asset montrant un "
                "client réel exige un consentement signé.",
    'revoque': "Consentement révoqué : l'asset ne peut plus être diffusé.",
    'expire': "Consentement expiré : renouveler avant toute diffusion.",
    'portee': "Portée de consentement insuffisante (photo/vidéo/témoignage/géo).",
}


# ══════════════════════════════════════════════════════════════════════════
# PUB126 — Divulgation « généré par IA » : garde DURE de la check-list.
# Un asset produit par une lane de fabrique IA (``creative_factory.
# AI_GENERATED_LANES``) et dont l'étiquette ``ai_generated`` n'est PAS posée ne
# passe JAMAIS la check-list — même si l'humain a coché toutes les règles (même
# mécanique que la garde consentement PUB75).
#
# CHAMP GRAPH DE DIVULGATION — VÉRIFIÉ, NON CONFIRMÉ (20/09/2026).
# La référence publique de l'objet AdCreative
# (https://developers.facebook.com/docs/marketing-api/reference/ad-creative/)
# n'expose AUCUN champ de divulgation IA documenté. Le seul candidat listé,
# ``generative_asset_spec`` (type ``AdCreativeGenerativeAssetSpec``), y est
# sans description : rien ne permet d'affirmer qu'il PORTE la divulgation.
# On ne devine donc PAS un nom de champ Graph (envoyer un paramètre inconnu =
# créatif rejeté, et écrire une divulgation dans le vide = pire qu'aucune) :
# ``GRAPH_AI_DISCLOSURE_FIELD`` reste VIDE tant que le champ n'est pas confirmé
# dans la doc, et les constructeurs de payload (PUB118/PUB123) n'ajoutent rien
# à la spec Graph pendant ce temps. La divulgation voyage en INTERNE dans le
# payload (clé ``ai_generated``), prête à être mappée le jour où le champ est
# confirmé — un seul endroit à changer.
# ══════════════════════════════════════════════════════════════════════════
AI_DISCLOSURE_BLOCK = 'etiquette_ia_manquante'
AI_DISCLOSURE_BLOCK_LABEL = (
    "Étiquette « généré par IA » manquante : cet asset vient d'une lane de "
    "génération — la divulgation est exigée par Meta avant toute diffusion.")
GRAPH_AI_DISCLOSURE_FIELD = ''


def ai_disclosure_block_reason(asset):
    """PUB126 — ``AI_DISCLOSURE_BLOCK`` si l'asset DEVRAIT porter l'étiquette IA
    (sa lane génère de l'IA, ou il dérive d'un asset IA) et ne la porte pas ;
    sinon ``None``. Un asset non-IA (chantier, UGC réel, upload) n'a aucune
    contrainte — et n'est jamais sur-étiqueté."""
    from . import creative_factory

    should_disclose = creative_factory.asset_is_ai_generated(
        asset.source_lane, asset.parent)
    if should_disclose and not asset.ai_generated:
        return AI_DISCLOSURE_BLOCK
    return None


def ai_disclosure_payload(asset):
    """PUB126 — Fragment de divulgation à PROPAGER dans un payload de création de
    créatif (PUB118 recombinaison DCO / PUB123 pont CreativeAsset→créatif).

    Renvoie toujours la clé INTERNE ``ai_generated`` (bool) — la divulgation
    suit l'asset de bout en bout, jusqu'à l'ad. Quand (et seulement quand) le
    champ Graph de divulgation sera confirmé, ``GRAPH_AI_DISCLOSURE_FIELD``
    portera son nom et le fragment l'ajoutera : aucun appelant à modifier."""
    disclosure = {'ai_generated': bool(asset.ai_generated)}
    if GRAPH_AI_DISCLOSURE_FIELD:
        disclosure[GRAPH_AI_DISCLOSURE_FIELD] = bool(asset.ai_generated)
    return disclosure


def asset_warnings(asset):
    """PUB83 — Avertissements NON BLOQUANTS de la check-list policy d'un asset.

    Aujourd'hui : vignette manquante sur un reel/explainer — la check-list
    signale qu'aucune vignette n'a été CHOISIE (le défaut « frame 0 » est un
    mauvais choix par défaut). Un statique n'a pas de vignette distincte (l'image
    EST la vignette) : pas d'avertissement. Renvoie une liste de dicts
    ``{key, label}`` (vide si aucun avertissement)."""
    from .models import CreativeAsset

    warnings = []
    video_types = (
        CreativeAsset.AssetType.REEL, CreativeAsset.AssetType.EXPLAINER)
    if asset.asset_type in video_types and not asset.thumbnail_key:
        warnings.append({
            'key': 'thumbnail_missing',
            'label': ("Vignette manquante : choisissez une vignette "
                      "(jamais la frame 0 par défaut)."),
        })
    return warnings


def record_policy_check(asset, *, confirmed_keys, checked_by=None, now=None):
    """Enregistre la confirmation HUMAINE règle par règle sur ``asset``.

    ``passed`` devient vrai UNIQUEMENT si toutes les clés de règles INTERDITES
    de la policy sont dans ``confirmed_keys`` (l'humain atteste que le créatif ne
    les enfreint pas). Le système n'évalue jamais le contenu lui-même — il
    enregistre le jugement humain. Estampille ``policy_stamp`` et sauvegarde.

    PUB75 — GARDE CONSENTEMENT (CNDP) : un asset marqué « client réel »
    (``depicts_real_client``) ne passe JAMAIS sans un ``ConsentRecord`` actif
    couvrant ses portées requises — même si l'humain a coché toutes les règles.
    La raison de blocage est consignée dans le tampon (``consent_block``).

    PUB126 — GARDE DIVULGATION IA : un asset issu d'une lane de génération dont
    l'étiquette ``ai_generated`` n'est pas posée ne passe JAMAIS non plus
    (``ai_disclosure_block`` dans le tampon). Renvoie l'asset.
    """
    forbidden, _allowed = _policy_rules(asset.company)
    required = {r['key'] for r in forbidden}
    confirmed = set(confirmed_keys or [])
    passed = required.issubset(confirmed)
    # Garde consentement : bloque un asset client-réel sans consentement valable.
    consent_block = asset.consent_block_reason(now=now)
    if consent_block is not None:
        passed = False
    # PUB126 — garde divulgation IA : bloque un asset IA sans son étiquette.
    ai_block = ai_disclosure_block_reason(asset)
    if ai_block is not None:
        passed = False
    stamp_time = now or timezone.now()
    checked_at = (stamp_time.isoformat() if hasattr(stamp_time, 'isoformat')
                  else str(stamp_time))
    stamp = {
        'passed': passed,
        'rules_checked': sorted(confirmed),
        'checked_at': checked_at,
        'checked_by': (getattr(checked_by, 'id', checked_by)
                       if checked_by is not None else None),
    }
    if consent_block is not None:
        stamp['consent_block'] = consent_block
        stamp['consent_block_label'] = CONSENT_BLOCK_LABELS.get(
            consent_block, consent_block)
    if ai_block is not None:
        stamp['ai_disclosure_block'] = ai_block
        stamp['ai_disclosure_block_label'] = AI_DISCLOSURE_BLOCK_LABEL
    # PUB83 — avertissements NON BLOQUANTS (ex. vignette manquante) : consignés
    # dans le tampon sans jamais faire échouer la validation.
    warnings = asset_warnings(asset)
    if warnings:
        stamp['warnings'] = warnings
    asset.policy_stamp = stamp
    asset.save(update_fields=['policy_stamp', 'updated_at'])
    return asset


def revoke_consent(consent):
    """PUB75 — Retire de la rotation tous les assets liés à un consentement révoqué.

    Pour chaque ``CreativeAsset`` pointant ``consent``, dé-tamponne la policy
    (``policy_stamp.passed=False`` + ``consent_block='revoque'``) afin que le
    filtre de rotation existant (``asset__policy_stamp__passed=True``) l'exclue
    aussitôt — sans rien re-vérifier du contenu. Renvoie le nombre d'assets
    retirés. Idempotent : un asset déjà retiré pour cette raison n'est pas
    ré-écrit."""
    updated = 0
    for asset in consent.assets.all():
        stamp = dict(asset.policy_stamp or {})
        if stamp.get('passed') is False and stamp.get('consent_block') == 'revoque':
            continue
        stamp['passed'] = False
        stamp['consent_block'] = 'revoque'
        stamp['consent_block_label'] = CONSENT_BLOCK_LABELS['revoque']
        asset.policy_stamp = stamp
        asset.save(update_fields=['policy_stamp', 'updated_at'])
        updated += 1
    return updated
