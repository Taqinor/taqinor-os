"""ADSDEEP46 — Parseur de convention de nommage créative (PUR, AUCUN LLM).

Barre Motion (benchmark concurrent §2) : un « naming-convention parser + AI
tagging » lit le nom d'une ad Meta (ex. ``26_UGC_PAIN_ROI``) selon une
convention POSITIONNELLE configurable (ex. ``"DATE_FORMAT_HOOK_ANGLE"`` —
chaque segment du nom, DANS L'ORDRE, correspond au champ de même rang dans la
convention) et en extrait des tags hook/angle/format — sans aucun LLM (parsing
de chaîne pur, déterministe, testable sur fixtures). L'IA-tagging (catégorisation
sémantique du CONTENU créatif) reste explicitement HORS PÉRIMÈTRE (dossier
ADSDEEP, gated) ; ce module ne fait que découper une CHAÎNE.

Les tags atterrissent sur ``AdMirror`` (source ``name``, le nom Meta) et
``CreativeAsset`` (source ``file_key``, la bibliothèque maison n'a pas de
``name`` — le nom de FICHIER, sans chemin ni extension, joue ce rôle) via la
migration additive ADSDEEP46 (0027). :func:`retag_company_ads` /
:func:`retag_company_creative_assets` retro-taguent les objets DÉJÀ
synchronisés.

Un nom mal formé (segment manquant, séparateur absent, champ hors
vocabulaire) ne lève JAMAIS d'exception : il produit simplement des tags
partiels ou vides — jamais un plantage de sync sur une convention de nommage
imparfaite (les comptes réels ne respectent jamais une convention à 100 %).
"""
from __future__ import annotations

import posixpath

# ── Vocabulaire de champs connus (hook/angle/format sont MATÉRIALISÉS en tags ;
# ``date`` sert de repère positionnel sans tag stocké ; PUB77 : ``language``
# devient une dimension positionnelle reconnue — normalisée en fr/ar-ma/amazigh,
# posée sur ``CreativeAsset.language`` par l'appelant, jamais un tag libre). ───
KNOWN_FIELDS = ('date', 'format', 'hook', 'angle', 'language')
TAG_FIELDS = ('hook', 'angle', 'format')

DEFAULT_DELIMITER = '_'
DEFAULT_CONVENTION = 'DATE_FORMAT_HOOK_ANGLE'

# PUB77 — Alias de langue → clé canonique (``CreativeAsset.Language``). Un
# segment inconnu → '' (langue non renseignée, jamais une valeur fabriquée).
LANGUAGE_ALIASES = {
    'fr': 'fr', 'french': 'fr', 'francais': 'fr', 'français': 'fr',
    'ar': 'ar-ma', 'ar-ma': 'ar-ma', 'arma': 'ar-ma', 'darija': 'ar-ma',
    'ary': 'ar-ma', 'arabe': 'ar-ma',
    'amazigh': 'amazigh', 'tz': 'amazigh', 'ber': 'amazigh',
    'tamazight': 'amazigh',
}


def normalize_language(segment):
    """PUB77 — Normalise un segment de langue en clé canonique fr/ar-ma/amazigh.
    Un segment vide/None/inconnu → '' (jamais une langue fabriquée)."""
    key = str(segment or '').strip().lower()
    return LANGUAGE_ALIASES.get(key, '')


def language_from_name(name, *, convention=DEFAULT_CONVENTION,
                       delimiter=DEFAULT_DELIMITER):
    """PUB77 — Langue canonique extraite d'un nom selon ``convention`` (nécessite
    un segment ``LANGUAGE`` dans la convention), ou '' si absente/inconnue."""
    parsed = parse_name(name, convention=convention, delimiter=delimiter)
    return normalize_language(parsed.get('language'))


def parse_convention(convention, *, delimiter=DEFAULT_DELIMITER):
    """Convention (``"DATE_FORMAT_HOOK_ANGLE"``) → liste ORDONNÉE de champs en
    minuscules (``['date', 'format', 'hook', 'angle']``). Une convention
    vide/None → liste vide (jamais une erreur). Un segment hors
    :data:`KNOWN_FIELDS` est conservé (minuscule) mais ne sera jamais lu par
    :func:`tags_from_name` (seuls hook/angle/format sont extraits en tags)."""
    if not convention:
        return []
    return [seg.strip().lower() for seg in str(convention).split(delimiter)
            if seg.strip()]


def parse_name(
        name, *, convention=DEFAULT_CONVENTION, delimiter=DEFAULT_DELIMITER):
    """Parse ``name`` POSITIONNELLEMENT selon ``convention`` : renvoie un dict
    ``{champ: segment}`` UNIQUEMENT pour les positions COUVERTES par le nom —
    un nom plus court que la convention laisse les champs en trop ABSENTS du
    dict (jamais une valeur vide fabriquée pour combler). ``name`` vide/None →
    ``{}`` (jamais une erreur)."""
    if not name:
        return {}
    # La convention (``DATE_FORMAT_HOOK_ANGLE``) est TOUJOURS séparée par ``_`` —
    # jamais par le ``delimiter`` du NOM (qui, lui, peut valoir ``-``, etc.).
    fields = parse_convention(convention)
    if not fields:
        return {}
    segments = str(name).split(delimiter)
    parsed = {}
    for field, segment in zip(fields, segments):
        segment = segment.strip()
        if segment:
            parsed[field] = segment
    return parsed


def tags_from_name(
        name, *, convention=DEFAULT_CONVENTION, delimiter=DEFAULT_DELIMITER):
    """Tags hook/angle/format extraits de ``name`` — les SEULS champs
    matérialisés en base (ADSDEEP46). Renvoie toujours
    ``{'hook_tag': str, 'angle_tag': str, 'format_tag': str}`` — chaîne VIDE
    (jamais ``None``) pour un champ non couvert, cohérent avec le
    ``default=''`` des champs modèle."""
    parsed = parse_name(name, convention=convention, delimiter=delimiter)
    return {
        'hook_tag': parsed.get('hook', ''),
        'angle_tag': parsed.get('angle', ''),
        'format_tag': parsed.get('format', ''),
    }


def _basename_without_extension(path):
    """Nom de fichier SANS chemin ni extension (ex.
    ``'societe/2026_UGC_PAIN_ROI.mp4'`` → ``'2026_UGC_PAIN_ROI'``). Chemin
    vide/None → chaîne vide (jamais une erreur)."""
    normalized = str(path or '').replace('\\', '/')
    base = posixpath.basename(normalized)
    stem, _sep, _ext = base.rpartition('.')
    return stem or base


def _apply_tags(obj, tags):
    """Écrit ``tags`` (``{hook_tag, angle_tag, format_tag}``) sur ``obj`` s'ils
    diffèrent des valeurs actuelles ; renvoie ``True`` si une écriture a eu
    lieu (jamais un ``save()`` inutile sur un objet déjà à jour)."""
    changed = any(getattr(obj, key) != value for key, value in tags.items())
    if not changed:
        return False
    for key, value in tags.items():
        setattr(obj, key, value)
    obj.save(update_fields=[*tags.keys(), 'updated_at'])
    return True


def retag_company_ads(
        company, *, convention=DEFAULT_CONVENTION,
        delimiter=DEFAULT_DELIMITER, queryset=None):
    """ADSDEEP46 — Retro-tague les ``AdMirror`` DÉJÀ synchronisés d'une société
    (relit ``name``, ré-écrit hook_tag/angle_tag/format_tag). Idempotent : un
    ad déjà à jour n'est pas ré-écrit. Company-scopé par défaut (``queryset``
    permet de restreindre l'appelant, ex. commande de gestion ciblée). Renvoie
    le nombre d'ads EFFECTIVEMENT mis à jour."""
    from .models import AdMirror

    qs = (queryset if queryset is not None
          else AdMirror.objects.filter(company=company))
    updated = 0
    for ad in qs:
        tags = tags_from_name(
            ad.name, convention=convention, delimiter=delimiter)
        if _apply_tags(ad, tags):
            updated += 1
    return updated


def retag_company_creative_assets(
        company, *, convention=DEFAULT_CONVENTION,
        delimiter=DEFAULT_DELIMITER, queryset=None):
    """ADSDEEP46 — Retro-tague les ``CreativeAsset`` de la bibliothèque MAISON
    (pas de ``name`` Meta : le nom de fichier ``file_key``, sans chemin ni
    extension, sert de source au parseur). Même contrat d'idempotence que
    :func:`retag_company_ads`."""
    from .models import CreativeAsset

    qs = (queryset if queryset is not None
          else CreativeAsset.objects.filter(company=company))
    updated = 0
    for asset in qs:
        stem = _basename_without_extension(asset.file_key)
        tags = tags_from_name(
            stem, convention=convention, delimiter=delimiter)
        if _apply_tags(asset, tags):
            updated += 1
    return updated
