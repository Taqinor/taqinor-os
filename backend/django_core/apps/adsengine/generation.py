"""AGEN2 — Génération créative ANCRÉE sur la table de faits.

dd-assumption-engine §10.2 point 1 : « Génération ANCRÉE sur la table de faits
(citations par claim) ». C'est la PREMIÈRE couche de la pile de sécurité
(dd-assumption-engine §10.1, Palier A) : à partir d'un *seed-brief* (« quelques
mots »), de composants approuvés et de la table de faits PUBLIÉE d'une société,
on produit des variantes texte/statiques dont **CHAQUE chiffre cite une
``FactEntry``** de la version publiée. Un chiffre non cité fait ÉCHOUER la
variante — jamais un chiffre inventé n'atteint un asset.

Contrat de sûreté (comme ``creative_factory``) :
  * **key-gated, NO-OP sans clé** : sans ``ADSENGINE_GEN_API_KEY`` et sans
    générateur injecté, ``generate_grounded_variants`` ne fait AUCUN appel
    réseau et renvoie un résultat vide (``enabled=False``).
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

import logging
import os
import re

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


def _published_facts(company):
    """(table publiée, {clé: FactEntry}) de la société, ou (None, {})."""
    table = FactTable.published_for(company)
    if table is None:
        return None, {}
    return table, {e.cle: e for e in table.entries.all()}


def _default_generator():
    """Générateur IA réel — construit UNIQUEMENT si la clé est posée.

    Renvoie ``None`` sans la clé (NO-OP). Le jour où une clé existe, ce chemin
    fera l'appel LLM ancré ; il reste volontairement inerte ici (aucune
    dépendance pip, aucun endpoint en dur) — la génération réelle est injectée
    en attendant."""
    if not os.environ.get(GEN_ENV_KEY):
        return None

    def _generator(context):  # pragma: no cover - chemin réseau réel
        logger.info(
            'generation: clé %s présente mais aucun backend LLM câblé — '
            'aucune variante émise (injecter un générateur).', GEN_ENV_KEY)
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


def generate_grounded_variants(company, seed_brief, *, components=None,
                               asset_type=CreativeAsset.AssetType.STATIC,
                               generator=None, max_variants=3,
                               create_assets=True, source_lane='gen'):
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

    table, facts = _published_facts(company)
    context = {
        'seed_brief': (seed_brief or '').strip(),
        'components': list(components or []),
        'facts': [
            {'cle': e.cle, 'valeur': e.valeur, 'unite': e.unite}
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
                policy_stamp={},  # PENDING — jamais auto-validé
            )
            entry['asset_id'] = asset.id
            assets.append(asset)
        elif not report['grounded']:
            rejected.append(entry)
        variants_report.append(entry)

    return {
        'enabled': True,
        'table_version': table.version if table else None,
        'variants': variants_report,
        'assets': assets,
        'rejected': rejected,
    }
