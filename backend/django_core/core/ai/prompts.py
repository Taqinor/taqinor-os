"""NTAI5 — Bibliothèque de prompts : défaut CODE + surcharge par société.

Un prompt est une décision MÉTIER (ton, longueur, ce qu'on promet ou pas) qui
n'a aucune raison d'exiger un déploiement pour changer. Ce module pose la
paire :

  * le **défaut code** — enregistré à l'import par la feature qui l'utilise
    (:func:`register_default_prompt`), versionné dans git, toujours présent ;
  * la **surcharge société** — résolue par un résolveur enregistré par
    ``apps.ai_governance`` (:func:`register_prompt_resolver`).

Sans surcharge (et sans app de gouvernance installée), :func:`render_prompt`
rend EXACTEMENT le défaut code : le comportement est byte-identique à l'avant
NTAI5. ``core`` ne connaît ici aucun modèle — seulement une fonction.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

#: Défauts code, par clé de prompt (``'ai.rediger.email'``…).
_DEFAULTS: dict[str, str] = {}

#: Résolveur de surcharge ``fn(company, cle) -> str | None`` (facultatif).
_RESOLVER = None

#: Placeholder ``{{champ}}`` (espaces tolérés).
_RE_PLACEHOLDER = re.compile(r'{{\s*([a-zA-Z0-9_]+)\s*}}')


def register_default_prompt(cle: str, corps: str) -> str:
    """Enregistre (ou remplace) le défaut code d'une clé de prompt."""
    _DEFAULTS[str(cle)] = corps or ''
    return corps


def default_prompt(cle: str) -> str | None:
    """Défaut code d'une clé, ou ``None`` si la clé est inconnue."""
    return _DEFAULTS.get(str(cle))


def available_prompts() -> list:
    """Clés de prompt connues du code (triées)."""
    return sorted(_DEFAULTS)


def register_prompt_resolver(fn):
    """Enregistre le résolveur de surcharges société (une seule fois)."""
    global _RESOLVER
    _RESOLVER = fn
    return fn


def prompt_resolver():
    """Résolveur enregistré (ou ``None``)."""
    return _RESOLVER


def effective_prompt(company, cle: str) -> tuple[str, str]:
    """``(corps, origine)`` — ``origine`` ∈ ``'societe'`` | ``'code'``.

    Une surcharge vide ou illisible retombe sur le défaut code : on préfère un
    prompt correct à un prompt absent."""
    if _RESOLVER is not None and company is not None:
        try:
            surcharge = _RESOLVER(company, cle)
        except Exception:  # noqa: BLE001 — une surcharge illisible ne casse rien
            logger.warning('core.ai.prompts: surcharge illisible (%s)', cle,
                           exc_info=True)
            surcharge = None
        if surcharge:
            return surcharge, 'societe'
    defaut = _DEFAULTS.get(str(cle))
    if defaut is None:
        raise KeyError(f"Prompt inconnu : {cle!r}")
    return defaut, 'code'


def render_prompt(company, cle: str, context: dict | None = None) -> str:
    """Rend le prompt ``cle`` pour ``company``, placeholders remplacés.

    ``{{champ}}`` est remplacé par ``context['champ']`` ; un champ ABSENT est
    remplacé par une chaîne vide (jamais une exception, jamais un ``{{champ}}``
    laissé dans le texte envoyé au modèle — ce serait une consigne parasite).
    """
    corps, _origine = effective_prompt(company, cle)
    valeurs = context or {}

    def _remplacer(match):
        valeur = valeurs.get(match.group(1), '')
        return '' if valeur is None else str(valeur)

    return _RE_PLACEHOLDER.sub(_remplacer, corps)


def placeholders(corps: str) -> list:
    """Placeholders déclarés par un corps de prompt (ordre d'apparition)."""
    vus = []
    for nom in _RE_PLACEHOLDER.findall(corps or ''):
        if nom not in vus:
            vus.append(nom)
    return vus
