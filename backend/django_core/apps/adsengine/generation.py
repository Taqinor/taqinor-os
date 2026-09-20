"""AGEN2 — Génération créative ANCRÉE sur la table de faits.

dd-assumption-engine §10.2 point 1 : « Génération ANCRÉE sur la table de faits
(citations par claim) ». C'est la PREMIÈRE couche de la pile de sécurité
(dd-assumption-engine §10.1, Palier A) : à partir d'un *seed-brief* (« quelques
mots »), de composants approuvés et de la table de faits PUBLIÉE d'une société,
on produit des variantes texte/statiques dont **CHAQUE chiffre cite une
``FactEntry``** de la version publiée. Un chiffre non cité fait ÉCHOUER la
variante — jamais un chiffre inventé n'atteint un asset.

Contrat de sûreté (comme ``creative_factory``) :
  * **key-gated, NO-OP sans clé** : sans ``ADSENGINE_GEN_API_KEY``, sans son
    repli ``GROQ_API_KEY`` (PUB124) et sans générateur injecté,
    ``generate_grounded_variants`` ne fait AUCUN appel réseau et renvoie un
    résultat vide (``enabled=False``) — golden byte-identique.
  * les variantes conformes deviennent des ``CreativeAsset`` en **stamp policy
    PENDING** (``policy_stamp={}``) : elles ne peuvent pas partir en production
    tant que la check-list humaine (ENG16) + le routeur de paliers (AGEN6) ne
    les ont pas validées.
  * **AUCUNE dépendance pip nouvelle** ; le générateur réel (le jour où une clé
    est posée) est injectable — les tests injectent un générateur mock.

La whitelist numérique DURE aux formats FR (AGEN3, ``claim_check.py``) est le
vérificateur autoritaire consommé par le routeur ; ce module fait sa PROPRE
garde d'ancrage minimale (tout nombre du texte doit être couvert par une
citation) pour ne jamais émettre un asset non ancré, même construit isolément.
"""
from __future__ import annotations

import json
import logging
import os
import re

from . import claim_check, creative_factory
from .models import CreativeAsset, FactTable

logger = logging.getLogger(__name__)

# Clé d'environnement qui active le générateur IA réel. Absente → NO-OP.
GEN_ENV_KEY = 'ADSENGINE_GEN_API_KEY'

# Nombre FR : chiffres avec séparateurs de milliers (espace/insécable) et
# décimale virgule OU point (« 12 000 », « 1 234,56 », « 3.5 », « 82 »).
_NUMBER_RE = re.compile(r'\d[\d  .,]*\d|\d')


class GroundingError(ValueError):
    """Levée si une variante porte un chiffre sans citation valide."""


def _digits(text):
    """Suite de chiffres nue d'un fragment numérique (« 12 000 » → « 12000 »)."""
    return re.sub(r'\D', '', text or '')


def _published_facts(company, *, region=None):
    """(table publiée, {clé: FactEntry}) de la société, ou (None, {}).

    PUB85 — Résolution RÉGIONALE : on part des faits NATIONAUX (``region=''``),
    puis, si une ``region`` (ville) est demandée, on SURCHARGE chaque clé par la
    valeur régionale VÉRIFIÉE quand elle existe (irradiation/tarif local). Une
    ville sans fait régional garde donc la valeur nationale (jamais un chiffre
    local inventé). Comparaison de région insensible à la casse/espaces."""
    table = FactTable.published_for(company)
    if table is None:
        return None, {}
    entries = list(table.entries.all())
    facts = {}
    for e in entries:
        if not (getattr(e, 'region', '') or '').strip():
            facts[e.cle] = e  # base nationale
    if region:
        key = region.strip().lower()
        for e in entries:
            if (getattr(e, 'region', '') or '').strip().lower() == key:
                facts[e.cle] = e  # surcharge régionale vérifiée
    return table, facts


# ═════════════════════════════════════════════════════════════════════════════
# PUB124 — Backend LLM RÉEL (endpoint chat-completions OpenAI-compatible)
# ═════════════════════════════════════════════════════════════════════════════
# Le générateur par défaut restait inerte MÊME avec sa clé : le pipeline PUB16
# tournait donc à vide. On câble ici un appel chat-completions compatible OpenAI
# (Groq), avec le MÊME pattern que l'unique autre appelant LLM du dépôt
# (``apps/qhse/services.py`` : ``requests`` — déjà une dépendance —, endpoint
# ``/openai/v1/chat/completions``, ``temperature=0``,
# ``response_format={'type': 'json_object'}``). Aucune dépendance pip nouvelle,
# aucun SDK.
#
# CLÉ : ``ADSENGINE_GEN_API_KEY`` d'abord (clé DÉDIÉE au moteur pub), sinon
# ``GROQ_API_KEY`` (déjà posée sur le serveur pour le chatbot/SQL-agent — free
# tier, 0 MAD). AUCUNE clé ⇒ NO-OP strictement inchangé (golden byte-identique).
GEN_FALLBACK_ENV_KEY = 'GROQ_API_KEY'
GEN_MODEL_ENV_KEY = 'ADSENGINE_GEN_MODEL'
GEN_BASE_URL_ENV_KEY = 'ADSENGINE_GEN_BASE_URL'

# Endpoint + modèle par DÉFAUT : exactement ceux déjà utilisés par
# ``apps/qhse/services.py`` (valeurs du dépôt, pas une nouveauté inventée ici).
# Les deux sont surchargeables par variable d'environnement — un modèle
# retiré du catalogue du fournisseur se remplace sans toucher au code.
DEFAULT_GEN_BASE_URL = 'https://api.groq.com/openai/v1'
DEFAULT_GEN_MODEL = 'llama-3.1-8b-instant'
GEN_TIMEOUT_SECONDS = 20

# Pattern de variation — « hook-first 3-3-3 ». SOURCE ET NIVEAU DE PREUVE
# (docs/engine/research/scope-science.md §3, tier UNVERIFIED) : « 3-3-3 » =
# 3 concepts × 3 variations × 3 accroches (Pilothouse Digital, chiffre de
# case-study d'agence NON audité) ; « hook first » = l'ORDRE de priorité des
# leviers de test (accroche → format visuel → angle → CTA → longueur de copie),
# la seule recommandation qui revient chez toutes les sources. On n'en tire
# AUCUN chiffre de performance : seulement la CONSIGNE de faire varier
# l'accroche d'abord.
GEN_VARIATION_PATTERN = 'hook-first 3-3-3'

SYSTEM_PROMPT_FR = (
    "Tu rédiges des variantes de publicité pour un installateur solaire au "
    "Maroc. Tu écris dans la langue du brief (français par défaut).\n"
    "RÈGLE ABSOLUE — CHIFFRES : tu n'as le droit d'écrire QUE des chiffres "
    "présents dans la liste « faits » fournie, et CHAQUE chiffre écrit doit "
    "être cité dans « claims » par la clé du fait (« fact_key ») d'où il "
    "vient. Si un chiffre n'est pas dans les faits, tu ne l'écris pas — tu "
    "reformules sans chiffre. N'invente jamais un prix, un pourcentage, une "
    "durée, une puissance ni une quantité. N'ajoute aucun chiffre décoratif "
    "(ni année, ni numéro de téléphone, ni note sur 5).\n"
    "VARIATION — fais varier d'abord l'ACCROCHE (hook), puis l'angle : chaque "
    "variante doit porter une accroche NETTEMENT différente des autres, pas une "
    "reformulation.\n"
    "SORTIE — réponds UNIQUEMENT par un objet JSON valide de la forme :\n"
    '{"variants": [{"hook_text": "…", "primary_text": "…", "cta": "…", '
    '"hook_tag": "…", "angle_tag": "…", '
    '"claims": [{"fact_key": "…"}]}]}\n'
    "« hook_tag » et « angle_tag » sont des étiquettes courtes en MAJUSCULES "
    "sans espace (ex. FACTURE, ROI). Aucun texte hors du JSON."
)

# Clés de variante retenues de la sortie LLM (tout le reste est IGNORÉ : un
# modèle bavard ne doit jamais pouvoir écrire un champ de modèle inattendu).
_VARIANT_TEXT_KEYS = ('hook_text', 'primary_text', 'cta', 'hook_tag',
                      'angle_tag', 'format_tag', 'asset_type')


class GenerationBackendError(RuntimeError):
    """PUB124 — Échec de l'appel au backend LLM (réseau / clé / réponse
    illisible). Jamais propagée au pipeline : ``_default_generator`` la capture
    et renvoie zéro variante (aucun crash, aucune variante fabriquée)."""


def resolve_api_key():
    """Clé du backend de génération : ``ADSENGINE_GEN_API_KEY`` sinon
    ``GROQ_API_KEY``. Renvoie ``(clé, nom_de_variable)`` — ``('', '')`` si
    aucune (NO-OP). La VALEUR n'est jamais journalisée."""
    for name in (GEN_ENV_KEY, GEN_FALLBACK_ENV_KEY):
        value = (os.environ.get(name) or '').strip()
        if value:
            return value, name
    return '', ''


def gen_base_url():
    """Base de l'API compatible OpenAI (surchargée par ``ADSENGINE_GEN_BASE_URL``)."""
    return ((os.environ.get(GEN_BASE_URL_ENV_KEY) or '').strip()
            or DEFAULT_GEN_BASE_URL).rstrip('/')


def gen_model():
    """Modèle de génération (surchargé par ``ADSENGINE_GEN_MODEL``)."""
    return ((os.environ.get(GEN_MODEL_ENV_KEY) or '').strip()
            or DEFAULT_GEN_MODEL)


def backend_status():
    """État du backend de génération, SANS jamais exposer la clé : ``{enabled,
    key_env, model, base_url, pattern}``. Consommé par l'audit (PUB124) et
    lisible par une vue de diagnostic."""
    _key, key_env = resolve_api_key()
    return {
        'enabled': bool(key_env),
        'key_env': key_env,
        'model': gen_model(),
        'base_url': gen_base_url(),
        'pattern': GEN_VARIATION_PATTERN,
    }


def build_messages(context):
    """Messages chat-completions d'un contexte de génération.

    Le message utilisateur ne porte QUE : le *seed-brief*, la région demandée,
    les slots de composants approuvés, et les FAITS DE LA TABLE PUBLIÉE
    (``cle``/``valeur``/``unite``/``region``). Aucun autre chiffre, aucune donnée
    d'une autre société, aucun historique — le modèle ne peut citer que ce qu'on
    lui donne, et ``claim_check`` tranche ensuite (whitelist dure)."""
    payload = {
        'brief': context.get('seed_brief', ''),
        'region': context.get('region'),
        'composants_approuves': list(context.get('components') or []),
        'faits': [
            {'cle': f.get('cle'), 'valeur': f.get('valeur'),
             'unite': f.get('unite'), 'region': f.get('region', '')}
            for f in (context.get('facts') or [])
        ],
        'nombre_de_variantes': int(context.get('max_variants') or 1),
        'type_asset': context.get('asset_type'),
    }
    return [
        {'role': 'system', 'content': SYSTEM_PROMPT_FR},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
    ]


def parse_variants(content, *, max_variants=3):
    """Parse la sortie LLM en variantes exploitables (jamais une exception).

    Accepte ``{"variants": [...]}`` ou une liste nue. Chaque entrée non-dict est
    ignorée ; seules les clés attendues sont retenues (un modèle bavard n'écrit
    jamais un champ de modèle inattendu) ; ``claims`` est normalisé en liste de
    ``{'fact_key': str}``. Une réponse illisible renvoie ``[]`` — le pipeline
    produit alors zéro variante, jamais une variante fabriquée."""
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except (TypeError, ValueError):
        logger.warning('generation: sortie LLM non JSON — zéro variante.')
        return []
    if isinstance(data, dict):
        raw = data.get('variants')
    else:
        raw = data
    if not isinstance(raw, list):
        logger.warning(
            'generation: sortie LLM sans liste « variants » — zéro variante.')
        return []

    variants = []
    for item in raw[:max(1, int(max_variants or 1))]:
        if not isinstance(item, dict):
            continue
        variant = {}
        for key in _VARIANT_TEXT_KEYS:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                variant[key] = value.strip()
        claims = []
        for claim in (item.get('claims') or []):
            if isinstance(claim, dict):
                fact_key = claim.get('fact_key')
            else:
                fact_key = claim
            if isinstance(fact_key, str) and fact_key.strip():
                claims.append({'fact_key': fact_key.strip()})
        variant['claims'] = claims
        if variant.get('hook_text') or variant.get('primary_text'):
            variants.append(variant)
    return variants


def call_llm_variants(context, *, api_key=None, timeout=GEN_TIMEOUT_SECONDS):
    """Appelle le backend chat-completions et renvoie les variantes parsées.

    Lève ``GenerationBackendError`` (réseau, statut HTTP, réponse sans contenu).
    ``requests`` est déjà une dépendance du projet — aucun SDK ajouté."""
    import requests

    key = api_key or resolve_api_key()[0]
    if not key:
        raise GenerationBackendError(
            f'{GEN_ENV_KEY} / {GEN_FALLBACK_ENV_KEY} absents — aucun appel.')
    url = f'{gen_base_url()}/chat/completions'
    try:
        resp = requests.post(
            url,
            headers={'Authorization': f'Bearer {key}',
                     'Content-Type': 'application/json'},
            json={
                'model': gen_model(),
                'messages': build_messages(context),
                'temperature': 0,
                'response_format': {'type': 'json_object'},
            },
            timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 — traduit en erreur de backend
        raise GenerationBackendError(
            f'Appel au backend de génération échoué : {exc}') from exc
    try:
        content = data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise GenerationBackendError(
            'Réponse du backend de génération sans contenu exploitable.'
        ) from exc
    return parse_variants(
        content, max_variants=context.get('max_variants') or 3)


def _default_generator():
    """Générateur IA réel — construit UNIQUEMENT si une clé est posée.

    Renvoie ``None`` sans AUCUNE clé (``ADSENGINE_GEN_API_KEY`` ni
    ``GROQ_API_KEY``) : le NO-OP de ``generate_grounded_variants`` reste alors
    strictement inchangé (golden byte-identique). Avec une clé, l'appel réel est
    fait ; un échec de backend est journalisé et rend ZÉRO variante — jamais une
    exception qui casserait le beat, jamais une variante fabriquée."""
    key, key_env = resolve_api_key()
    if not key:
        return None

    def _generator(context):
        try:
            return call_llm_variants(context, api_key=key)
        except GenerationBackendError as exc:
            logger.warning(
                'generation: backend LLM (clé %s, modèle %s) indisponible — '
                'zéro variante. %s', key_env, gen_model(), exc)
            return []

    return _generator


def _extract_numbers(text):
    """Fragments numériques bruts trouvés dans un texte (formats FR)."""
    return [m.group(0).strip() for m in _NUMBER_RE.finditer(text or '')]


def _check_variant_grounding(variant, facts):
    """Vérifie l'ancrage d'UNE variante candidate contre la table publiée.

    Renvoie un rapport ``{grounded, claims, uncited_numbers, unknown_keys}``.
    Règle DURE : tout nombre du texte non couvert par une citation valide, ou
    toute citation vers une clé inexistante, ⇒ ``grounded=False``.
    """
    text = ' '.join(
        str(variant.get(f) or '')
        for f in ('hook_text', 'primary_text', 'cta'))
    declared = variant.get('claims') or []

    covered = set()
    checked_claims = []
    unknown_keys = []
    for claim in declared:
        key = (claim or {}).get('fact_key')
        entry = facts.get(key)
        if entry is None:
            unknown_keys.append(key)
            checked_claims.append(
                {'fact_key': key, 'verified': False, 'reason': 'clé absente'})
            continue
        checked_claims.append({
            'fact_key': key,
            'verified': True,
            'valeur': entry.valeur,
            'unite': entry.unite,
            'source': entry.source,
            # PUB85 — trace si la valeur citée est régionale ('' = nationale).
            'region': getattr(entry, 'region', '') or '',
        })
        covered.update(_digits(d) for d in _extract_numbers(entry.valeur))

    uncited = []
    for frag in _extract_numbers(text):
        if _digits(frag) not in covered:
            uncited.append(frag)

    grounded = not uncited and not unknown_keys
    return {
        'grounded': grounded,
        'claims': checked_claims,
        'uncited_numbers': uncited,
        'unknown_keys': unknown_keys,
    }


def _hard_claim_violations(verdict, checked_claims):
    """PUB124 — Violations ``claim_check`` qui sont VRAIMENT un chiffre
    invérifiable (celles qui font rejeter la variante).

    ``claim_check`` exige que l'unité écrite dans le texte COÏNCIDE avec celle
    du fait — unité COMPOSÉE COMPRISE depuis PUB-P8/C1 : son extracteur lit
    « 1750 kWh/kWc/an » EN ENTIER, plus seulement sa tête. La tolérance qui
    subsiste ici ne sert donc plus qu'un cas RÉEL : un fait dont la ``valeur``
    porte plusieurs nombres (« 1500 à 1750 ») qu'aucune ``FactEntry`` ne peut
    apparier numériquement, alors que la variante cite bien CE fait.

    La comparaison d'unités est une ÉGALITÉ À FRONTIÈRE de composantes
    (``claim_check.unit_components``), JAMAIS un préfixe :

      * « kWh » vaut « kWh » ✓ ;
      * « kW » ne vaut PAS « kWh » ni « kWh/kWc/an » ✗ — ce préfixe-là était le
        trou : un fait « 1750 kWh/kWc/an » cité « 1750 kW » passait ;
      * « MAD » ne vaut PAS « MAD/mois » ✗ — une mensualité vendue en prix flat
        est un mensonge de prix, pas une notation : si le fait porte une unité
        COMPOSÉE, le texte doit porter la composée ENTIÈRE, sinon la violation
        RESTE.

    Tout le reste reste une violation DURE : un chiffre absent des faits, ou le
    bon chiffre avec une MAUVAISE unité (« 82 MAD » citant un fait « 82 % » est
    un mensonge, pas une notation) — jamais toléré.
    """
    hard = []
    verified = [c for c in (checked_claims or []) if c.get('verified')]
    for violation in (verdict.get('violations') or []):
        digits = _digits(violation.get('fragment'))
        unit = claim_check.unit_components(violation.get('unit'))
        tolerated = False
        for claim in verified:
            if digits not in {_digits(f)
                              for f in _extract_numbers(claim.get('valeur'))}:
                continue
            fact_unit = claim_check.unit_components(claim.get('unite'))
            if unit and fact_unit and unit == fact_unit:
                tolerated = True
                break
        if not tolerated:
            hard.append(violation)
    return hard


def resolve_facts_for_region(company, region=None):
    """PUB85 — Faits publiés résolus pour une ``region`` (ville) : dict
    ``{clé: FactEntry}`` avec surcharge régionale sur le socle national. Utilitaire
    de lecture pour la génération ville-spécifique et le reporting."""
    _table, facts = _published_facts(company, region=region)
    return facts


def generate_grounded_variants(company, seed_brief, *, components=None,
                               asset_type=CreativeAsset.AssetType.STATIC,
                               generator=None, max_variants=3,
                               create_assets=True, source_lane='gen',
                               region=None):
    """Génère des variantes ANCRÉES depuis un *seed-brief* de quelques mots.

    * ``company`` — société propriétaire (multi-tenant : force le scope).
    * ``seed_brief`` — « quelques mots » d'intention (l'humain amorce).
    * ``components`` — composants approuvés (hooks/visuels) passés au contexte.
    * ``generator`` — callable ``context -> [variant_dict]`` (DI/tests). Absent :
      le générateur réel n'est construit que si ``ADSENGINE_GEN_API_KEY`` existe,
      sinon NO-OP.

    Chaque variante candidate est vérifiée : tout nombre doit citer une
    ``FactEntry`` publiée. Les variantes conformes deviennent des
    ``CreativeAsset`` PENDING (``policy_stamp={}``). Renvoie
    ``{enabled, table_version, variants[], assets[], rejected[]}`` — le rapport
    de claims par variante.
    """
    gen = generator if generator is not None else _default_generator()
    if gen is None:
        logger.info('generation: %s absent — no-op (aucune variante).',
                    GEN_ENV_KEY)
        return {
            'enabled': False, 'table_version': None,
            'variants': [], 'assets': [], 'rejected': [],
            'reason': f'{GEN_ENV_KEY} absent — génération désactivée',
        }

    table, facts = _published_facts(company, region=region)
    context = {
        'seed_brief': (seed_brief or '').strip(),
        'components': list(components or []),
        'region': (region or '').strip() or None,
        'facts': [
            {'cle': e.cle, 'valeur': e.valeur, 'unite': e.unite,
             'region': getattr(e, 'region', '') or ''}
            for e in facts.values()
        ],
        'asset_type': asset_type,
        'max_variants': max_variants,
    }

    candidates = list(gen(context) or [])[:max_variants]

    variants_report = []
    assets = []
    rejected = []
    for candidate in candidates:
        report = _check_variant_grounding(candidate, facts)
        # PUB124 — le vérificateur AUTORITAIRE (AGEN3 ``claim_check``, whitelist
        # numérique DURE) passe EN PLUS de la garde d'ancrage interne : son
        # verdict complet est persisté dans l'audit, et ses violations DURES
        # (cf. ``_hard_claim_violations``) font REJETER la variante. Les deux
        # gardes sont cumulatives, jamais alternatives.
        verdict = claim_check.verify_text(
            company, ' '.join(str(candidate.get(f) or '') for f in
                              ('hook_text', 'primary_text', 'cta')))
        hard = _hard_claim_violations(verdict, report['claims'])
        report['claim_verdicts'] = verdict
        report['claim_violations_dures'] = hard
        report['grounded'] = bool(report['grounded'] and not hard)
        entry = {
            'hook_text': candidate.get('hook_text', ''),
            'primary_text': candidate.get('primary_text', ''),
            'cta': candidate.get('cta', ''),
            'asset_type': candidate.get('asset_type', asset_type),
            **report,
        }
        if report['grounded'] and create_assets:
            asset = CreativeAsset.objects.create(
                company=company,
                asset_type=candidate.get('asset_type', asset_type),
                source_lane=source_lane,
                hook_text=candidate.get('hook_text', ''),
                primary_text=candidate.get('primary_text', ''),
                cta=candidate.get('cta', ''),
                hook_tag=candidate.get('hook_tag', ''),
                angle_tag=candidate.get('angle_tag', ''),
                format_tag=candidate.get('format_tag', ''),
                # PUB76 — trace la version de faits citée (fraîcheur/conformité).
                facts_version=(table.version if table else None),
                policy_stamp={},  # PENDING — jamais auto-validé
                # PUB126 — divulgation IA posée PAR LA LANE de fabrique : la
                # génération ancrée produit du texte IA, elle s'étiquette donc
                # toujours (et la check-list policy bloque un asset IA nu).
                ai_generated=creative_factory.lane_is_ai_generated(source_lane),
            )
            entry['asset_id'] = asset.id
            assets.append(asset)
        elif not report['grounded']:
            rejected.append(entry)
        variants_report.append(entry)

    return {
        'enabled': True,
        'table_version': table.version if table else None,
        'region': (region or '').strip() or None,
        'variants': variants_report,
        'assets': assets,
        'rejected': rejected,
    }
