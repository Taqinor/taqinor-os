"""AGEN3 — Vérificateur whitelist numérique DUR (aucun palier mou).

dd-assumption-engine §10.2 point 2 : « Whitelist numérique dure (regex+NER,
zéro palier mou) ». C'est le vérificateur AUTORITAIRE de la pile de sécurité :
il extrait CHAQUE nombre (+ son unité) d'un texte généré aux formats FR
(``1 234,56``, ``82 %``, ``12 000 MAD``, ``6,4 kWc``) et exige que chacun
corresponde EXACTEMENT (à la tolérance de config près) à une ``FactEntry`` de la
table de faits PUBLIÉE de la société. Un seul chiffre non trouvé ⇒ le texte est
BLOQUÉ, avec une raison FR — jamais un faux chiffre ne passe.

Contrat :
  * pas de table publiée + un texte qui contient des nombres ⇒ tout est bloqué
    (aucun passage par défaut).
  * l'extraction NER (spaCy) est un BONUS optionnel : si le paquet est absent,
    l'extraction regex FR suffit et reste le socle — aucune dépendance pip
    nouvelle n'est requise.
"""
from __future__ import annotations

import logging
import re

from .models import FactTable

logger = logging.getLogger(__name__)

# ── Config du vérificateur (tolérances + normalisation d'unités) ──────────────
# Tolérance = écart absolu maximal toléré entre le nombre du texte et la valeur
# de la FactEntry. Défaut 0 = correspondance EXACTE. Surchargeable par unité.
CLAIM_CHECK_CONFIG = {
    'default_tolerance': 0.0,
    'tolerances_by_unit': {
        # ex. : '%': 0.0 (exact). Renseigner ici pour desserrer une unité.
    },
    # Synonymes d'unités → forme canonique (comparaison insensible à la casse).
    'unit_aliases': {
        'mad': 'MAD', 'dh': 'MAD', 'dhs': 'MAD', 'dirham': 'MAD',
        'dirhams': 'MAD', 'da': 'MAD',
        '%': '%', 'pourcent': '%', 'pct': '%',
        'kwc': 'kWc', 'kwp': 'kWc', 'wc': 'Wc',
        'kwh': 'kWh', 'mwh': 'MWh',
        'kw': 'kW', 'mw': 'MW', 'w': 'W',
        'an': 'an', 'ans': 'an', 'année': 'an', 'années': 'an',
        'm³/h': 'm³/h', 'm3/h': 'm³/h', 'm³/j': 'm³/j', 'm3/j': 'm³/j',
    },
}

# Nombre FR : chiffres, séparateurs de milliers (espace/insécable), décimale
# virgule ou point. Le fragment DOIT commencer et finir par un chiffre (la
# ponctuation de fin de phrase n'est jamais capturée).
_NUMBER_RE = re.compile(r'\d[\d  .,]*\d|\d')
# TÊTE d'unité (unité simple, ou première composante d'une unité composée).
# L'ordre compte : les formes LONGUES d'abord (« kWh » AVANT « kW »), sinon
# « kWh » se lirait « kW » — la frontière même que PUB-P8/C1 restaure.
_UNIT_HEAD = (r'%|kWc|kWp|kWh|MWh|MAD|DHS?|dh|dhs|kW|MW|Wc|m³/[hj]|m3/[hj]|'
              r'années?|ans?')
# Composante qui SUIT un « / » dans une unité COMPOSÉE (« kWh/kWc/an »,
# « MAD/mois », « kWh/kWc/jour »). Elle n'est lue qu'APRÈS un « / » : aucun mot
# ordinaire de la phrase ne peut donc être avalé comme unité.
_UNIT_TAIL = (r'kWc|kWp|kWh|MWh|MAD|kW|MW|Wc|m³|m3|années?|ans?|mois|'
              r'jours?|h|j')
# Unité immédiatement collée/espacée après le nombre — unité COMPOSÉE COMPRISE.
# PUB-P8/C1 : lire l'unité « à moitié » (« kWh » pour un fait « kWh/kWc/an »)
# était la CAUSE du trou de tolérance côté génération (« 1750 kW » passait pour
# « 1750 kWh/kWc/an », « 500 MAD » pour « 500 MAD/mois »).
_UNIT_RE = re.compile(
    rf'\s*((?:{_UNIT_HEAD})(?:/(?:{_UNIT_TAIL}))*)',
    re.IGNORECASE)


def parse_fr_number(fragment):
    """« 1 234,56 » → 1234.56 ; « 12 000 » → 12000.0 ; None si illisible."""
    s = re.sub(r'[\s ]', '', fragment or '')  # milliers (espaces/insécables)
    s = s.replace(',', '.')
    if s.count('.') > 1:  # « 12.000.000 » ambigu → illisible
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _canon_unit(raw):
    """Forme canonique d'une unité (via ``unit_aliases``), '' si vide.

    Unité COMPOSÉE comprise : un alias couvrant l'unité ENTIÈRE gagne
    (« m3/h » → « m³/h ») ; sinon CHAQUE composante séparée par « / » est
    canonisée à son tour (« kwh/kwp/année » → « kWh/kWc/an »). La comparaison
    d'unités reste donc une ÉGALITÉ de composantes, jamais un préfixe."""
    if not raw:
        return ''
    text = str(raw).strip()
    aliases = CLAIM_CHECK_CONFIG['unit_aliases']
    whole = aliases.get(text.lower())
    if whole is not None:
        return whole
    parts = [p.strip() for p in text.split('/')]
    return '/'.join(aliases.get(p.lower(), p) for p in parts if p)


def unit_components(raw):
    """Composantes NORMALISÉES d'une unité : ``['kWh', 'kWc', 'an']``.

    PUB-P8/C1 — c'est la primitive de comparaison À FRONTIÈRE que les appelants
    utilisent au lieu d'un ``startswith`` : « kW » et « kWh » ne partagent AUCUNE
    composante, et « MAD » ne vaut pas « MAD/mois »."""
    canon = _canon_unit(raw)
    return [p for p in canon.split('/') if p] if canon else []


def extract_number_units(text):
    """Liste ``[{fragment, value, unit}]`` des nombres (+unités) d'un texte.

    Socle regex FR (toujours actif). L'extraction NER optionnelle ne fait
    qu'ajouter — elle ne retire jamais un nombre trouvé par le regex."""
    out = []
    for m in _NUMBER_RE.finditer(text or ''):
        frag = m.group(0).strip()
        value = parse_fr_number(frag)
        if value is None:
            continue
        tail = text[m.end():]
        um = _UNIT_RE.match(tail)
        unit = _canon_unit(um.group(1)) if um else ''
        out.append({'fragment': frag, 'value': value, 'unit': unit})
    return out


def _published_entries(company):
    """(table publiée, [(value, unit_canon, FactEntry)]) de la société."""
    table = FactTable.published_for(company)
    if table is None:
        return None, []
    parsed = []
    for entry in table.entries.all():
        val = parse_fr_number(entry.valeur)
        parsed.append((val, _canon_unit(entry.unite), entry))
    return table, parsed


def _tolerance_for(unit):
    cfg = CLAIM_CHECK_CONFIG
    return cfg['tolerances_by_unit'].get(unit, cfg['default_tolerance'])


def _matches(claim, entries):
    """La réclamation numérique correspond-elle à une FactEntry ?"""
    for val, unit, entry in entries:
        if val is None:
            continue
        if abs(val - claim['value']) > _tolerance_for(claim['unit']):
            continue
        # Unité : si le texte en porte une, elle DOIT coïncider avec le fait.
        if claim['unit'] and unit and claim['unit'] != unit:
            continue
        return entry
    return None


def verify_text(company, text):
    """Vérifie qu'un texte n'énonce AUCUN chiffre hors de la table publiée.

    Renvoie ``{ok, table_version, matched[], violations[]}``. ``ok`` n'est vrai
    que si CHAQUE nombre du texte correspond à une ``FactEntry`` publiée
    (whitelist dure). ``violations`` porte une raison FR par chiffre bloqué.
    """
    table, entries = _published_entries(company)
    version = table.version if table else None
    claims = extract_number_units(text)

    matched = []
    violations = []
    for claim in claims:
        entry = _matches(claim, entries) if entries else None
        if entry is not None:
            matched.append({
                'fragment': claim['fragment'],
                'unit': claim['unit'],
                'fact_key': entry.cle,
            })
        else:
            suffix = f' ({claim["unit"]})' if claim['unit'] else ''
            if version is None:
                reason = (
                    f'Chiffre « {claim["fragment"]} »{suffix} : aucune table '
                    f'de faits publiée — chiffre non vérifiable, bloqué.')
            else:
                reason = (
                    f'Chiffre « {claim["fragment"]} »{suffix} introuvable dans '
                    f'la table de faits publiée (v{version}) — bloqué.')
            violations.append({
                'fragment': claim['fragment'],
                'unit': claim['unit'],
                'reason': reason,
            })

    return {
        'ok': not violations,
        'table_version': version,
        'matched': matched,
        'violations': violations,
    }


def verify_asset(asset):
    """Vérifie hook + texte principal + CTA d'un ``CreativeAsset``."""
    text = ' '.join(filter(None, [
        asset.hook_text, asset.primary_text, asset.cta]))
    return verify_text(asset.company, text)
