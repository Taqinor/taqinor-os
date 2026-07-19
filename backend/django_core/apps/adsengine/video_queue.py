"""AGEN7 — Chaîne vidéo automatisée (script ancré faits → voix → montage).

dd-assumption-engine §10.2 point 1 : **génération ANCRÉE sur la table de faits**.
Ce module orchestre la fabrique d'un explainer vidéo de bout en bout, sans jamais
inventer un chiffre : le script est construit à partir de la ``FactTable`` PUBLIÉE
de la société (chaque ligne numérique CITE une ``FactEntry``) ; sans table
publiée, le script ne porte AUCUN chiffre (jamais de valeur fabriquée).

La chaîne réutilise les adaptateurs key-gated de la fabrique (ENG17,
``creative_factory``) — ``ElevenlabsAdapter`` (voix FR / darija, synchrone) puis
``Json2videoAdapter`` (assemblage de l'explainer) — exactement comme
``creative_factory.generate_variants`` chaîne fal/Templated. **NO-OP propre sans
clé** : sans ``JSON2VIDEO_API_KEY`` la chaîne ne produit rien (aucun appel
réseau), sans ``ELEVENLABS_API_KEY`` la voix est simplement omise.

RÈGLE DURE (§10.2 point 5) : l'asset produit naît TOUJOURS en **policy PENDING**
(``policy_stamp={}`` — garanti par ``CreativeFactoryAdapter.run``) et le créatif
vidéo reste au **palier B minimum en v1 — JAMAIS palier A** (``VIDEO_MIN_TIER``) :
un explainer généré passe donc obligatoirement la check-list humaine (ENG16) avant
toute diffusion. Un gabarit mis en QUARANTAINE par un rollback (AGEN9) ne peut
plus générer (``generation_audit.is_template_quarantined`` — no-op propre).

Aucune dépendance pip nouvelle ; aucune migration (champs/JSON existants).
"""
from __future__ import annotations

import logging

from .models import CreativeAsset

logger = logging.getLogger(__name__)

# §10.2 — le créatif vidéo reste au palier B minimum en v1 (jamais palier A :
# aucune autonomie de plus haut niveau qu'un statique généré ; il passe la même
# check-list humaine). Le palier A est explicitement REFUSÉ.
VIDEO_MIN_TIER = 'B'
_TIER_A = 'A'


def video_min_tier():
    """Palier minimum d'un créatif vidéo généré (toujours 'B' en v1)."""
    return VIDEO_MIN_TIER


def _reject_tier_a(tier):
    """Refuse tout palier A pour un créatif vidéo (v1 : palier B minimum). Un
    ``tier`` vide/None retombe sur le palier minimum. Renvoie le palier retenu."""
    normalized = str(tier or VIDEO_MIN_TIER).strip().upper() or VIDEO_MIN_TIER
    if normalized == _TIER_A:
        raise ValueError(
            "Un créatif vidéo généré ne peut pas être en palier A en v1 "
            "(palier B minimum) — il passe la check-list humaine comme tout "
            "autre créatif généré.")
    return normalized


def build_grounded_script(company, *, template_key='', beats=None):
    """AGEN7 — Construit un script ANCRÉ sur la table de faits PUBLIÉE.

    Chaque *beat* est un dict ``{'text': str, 'fact_key': str|None}``. Un beat
    portant une ``fact_key`` présente dans la table publiée est ancré : sa valeur
    citée est injectée depuis la ``FactEntry`` (jamais un chiffre inventé). Sans
    table publiée, AUCUN beat n'est ancré (les ``fact_key`` sont ignorées) —
    aucune valeur numérique ne peut alors apparaître.

    Renvoie ``{'template_key', 'facts_version', 'lines': [...], 'cited_keys':
    [...]}``. Fonction déterministe (lecture seule). ``beats`` par défaut : un
    unique beat d'ouverture non numérique (sûr même sans table).
    """
    from .models import FactTable

    published = FactTable.published_for(company)
    facts = {}
    facts_version = None
    if published is not None:
        facts_version = published.version
        facts = {e.cle: e for e in published.entries.all()}

    beats = beats if beats is not None else [
        {'text': "Passez au solaire avec Taqinor.", 'fact_key': None},
    ]

    lines = []
    cited_keys = []
    for beat in beats:
        text = str((beat or {}).get('text', '') or '')
        key = (beat or {}).get('fact_key')
        entry = facts.get(key) if key else None
        if entry is not None:
            unit = f' {entry.unite}' if entry.unite else ''
            # Ligne ancrée : la valeur VÉRIFIÉE est citée, jamais fabriquée.
            line = {
                'text': f'{text} {entry.valeur}{unit}'.strip(),
                'fact_key': key,
                'fact_value': entry.valeur,
                'fact_source': entry.source,
            }
            cited_keys.append(key)
        else:
            # Aucune citation disponible : la ligne reste NON numérique.
            line = {'text': text, 'fact_key': None}
        lines.append(line)

    return {
        'template_key': template_key,
        'facts_version': facts_version,
        'lines': lines,
        'cited_keys': cited_keys,
    }


def script_text(script):
    """Concatène le texte des lignes d'un script (pour la synthèse voix)."""
    return ' '.join(
        str(line.get('text', '')).strip()
        for line in (script or {}).get('lines', [])
        if str(line.get('text', '')).strip())


def _movie_spec(script, voice_asset):
    """Spécification d'assemblage JSON2Video (``input`` de l'adaptateur) portant
    le script ancré + la clé MinIO de la voix (si produite). Purement des
    DONNÉES : aucun appel réseau ici — l'adaptateur ``run`` s'en charge."""
    return {
        'template_key': (script or {}).get('template_key', ''),
        'facts_version': (script or {}).get('facts_version'),
        'cited_keys': list((script or {}).get('cited_keys', [])),
        'scenes': [
            {'text': line.get('text', ''), 'fact_key': line.get('fact_key')}
            for line in (script or {}).get('lines', [])
        ],
        'voiceover_key': getattr(voice_asset, 'file_key', '') or '',
    }


def generate_video(company, *, template_key='', script=None, voice_id='default',
                   tier=VIDEO_MIN_TIER, cost_cents=0, http_client=None):
    """AGEN7 — Chaîne vidéo de bout en bout : script ancré → voix → montage.

    1. **Quarantaine** : si le gabarit est en quarantaine (rollback AGEN9), no-op
       propre (renvoie ``None`` — un gabarit fautif ne régénère jamais).
    2. **Palier** : refuse le palier A (v1 = palier B minimum).
    3. **Script** ancré sur la table de faits publiée (aucun chiffre inventé).
    4. **Voix** (ElevenLabs, gated) : composant audio PENDING, ou omis sans clé.
    5. **Montage** (JSON2Video, gated) : l'explainer vidéo (``EXPLAINER``), lié à
       la voix (``parent``), TOUJOURS en policy PENDING (``policy_stamp={}``).

    NO-OP propre (renvoie ``None``) si JSON2Video est désactivé (pas de clé) ou si
    le gabarit est en quarantaine. Renvoie l'asset vidéo créé (pending) sinon.
    """
    from . import creative_factory as cf
    from . import generation_audit

    if generation_audit.is_template_quarantined(company, template_key):
        logger.info(
            'video_queue: gabarit « %s » en quarantaine — no-op (rollback AGEN9)',
            template_key)
        return None

    _reject_tier_a(tier)  # v1 : palier B minimum, jamais A.

    if script is None:
        script = build_grounded_script(company, template_key=template_key)

    # 4. Voix (composant audio) — gated, PENDING, omis proprement sans clé.
    voice_asset = None
    voice = cf.ElevenlabsAdapter()
    if voice.is_enabled():
        voice_asset = voice.run(
            company,
            {'asset_type': CreativeAsset.AssetType.EXPLAINER,
             'text': script_text(script), 'voice_id': voice_id},
            http_client=http_client)

    # 5. Montage (l'explainer vidéo) — gated ; sans clé, toute la chaîne no-ope.
    assembler = cf.Json2videoAdapter()
    if not assembler.is_enabled():
        logger.info('video_queue: JSON2Video désactivé (clé absente) — no-op')
        return None

    video = assembler.run(
        company,
        {'asset_type': CreativeAsset.AssetType.EXPLAINER,
         'input': _movie_spec(script, voice_asset),
         'cost_cents': cost_cents},
        http_client=http_client, parent=voice_asset)
    if video is not None:
        logger.info(
            'video_queue: explainer #%s généré (pending, palier %s, gabarit %s)',
            video.pk, VIDEO_MIN_TIER, template_key or '—')
    return video
