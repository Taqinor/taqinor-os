"""Registre des fournisseurs IA + sélection par capacité.

Le DÉFAUT de chaque capacité est le NO-OP : sans réglage explicite, rien
n'appelle l'extérieur. ``settings.AI_PROVIDERS`` est un dict
``{capacité: clé_fournisseur}`` qui sélectionne un fournisseur enregistré
(ex. ``{'ocr': 'zhipu', 'stt': 'whisper'}``). Une clé inconnue retombe sur le
NO-OP — on ne casse jamais.

Aucun import d'app métier ici : le registre est pur fondation.
"""
from __future__ import annotations

from django.conf import settings

from core.ai.providers import (
    LLMProvider,
    NoOpLLMProvider,
    NoOpOCRProvider,
    NoOpSTTProvider,
    NoOpVisionQAProvider,
    OCRProvider,
    STTProvider,
    VisionQAProvider,
)

# Interface de base attendue par capacité (sert à valider l'enregistrement).
_CAPABILITY_BASE = {
    'ocr': OCRProvider,
    'stt': STTProvider,
    'vision_qa': VisionQAProvider,
    'llm': LLMProvider,
}

# Fournisseur NO-OP par défaut de chaque capacité.
_NOOP = {
    'ocr': NoOpOCRProvider,
    'stt': NoOpSTTProvider,
    'vision_qa': NoOpVisionQAProvider,
    'llm': NoOpLLMProvider,
}

# Registre {capacité: {clé: classe}}. Pré-rempli avec les NO-OP.
_REGISTRY: dict[str, dict[str, type]] = {
    cap: {'noop': noop_cls} for cap, noop_cls in _NOOP.items()
}


def register_provider(provider_cls: type) -> type:
    """Enregistre une classe de fournisseur (déduit capacité + clé d'elle-même).

    Utilisable en décorateur. Lève si la capacité est inconnue ou si la classe
    ne dérive pas de l'interface de base de cette capacité."""
    cap = getattr(provider_cls, 'capability', None)
    key = getattr(provider_cls, 'key', None)
    if cap not in _CAPABILITY_BASE:
        raise ValueError(f"Capacité IA inconnue : {cap!r}")
    if not key:
        raise ValueError("Le fournisseur doit définir une `key`.")
    if not issubclass(provider_cls, _CAPABILITY_BASE[cap]):
        raise TypeError(
            f"{provider_cls.__name__} doit dériver de "
            f"{_CAPABILITY_BASE[cap].__name__}."
        )
    _REGISTRY.setdefault(cap, {})[key] = provider_cls
    return provider_cls


def _selected_key(capability: str) -> str:
    """Clé de fournisseur choisie pour ``capability`` (défaut 'noop')."""
    configured = getattr(settings, 'AI_PROVIDERS', None) or {}
    return configured.get(capability, 'noop')


def get_provider(capability: str):
    """Retourne une INSTANCE du fournisseur sélectionné pour ``capability``.

    Sélectionne selon ``settings.AI_PROVIDERS`` ; retombe sur le NO-OP si la
    capacité ou la clé est inconnue. De plus, si le fournisseur sélectionné
    n'est PAS configuré (clé absente), on retombe AUSSI sur le NO-OP — garantie
    « aucun appel sans config »."""
    if capability not in _CAPABILITY_BASE:
        raise ValueError(f"Capacité IA inconnue : {capability!r}")
    providers = _REGISTRY.get(capability, {})
    key = _selected_key(capability)
    cls = providers.get(key) or _NOOP[capability]
    instance = cls()
    # Garde-fou : un fournisseur sélectionné mais non configuré → NO-OP.
    if key != 'noop' and not instance.is_configured():
        return _NOOP[capability]()
    return instance


def is_capability_configured(capability: str) -> bool:
    """True si un fournisseur RÉEL (non NO-OP) est actif pour ``capability``."""
    provider = get_provider(capability)
    return getattr(provider, 'key', 'noop') != 'noop'


def available_providers(capability: str | None = None) -> dict:
    """Liste les clés enregistrées (toutes capacités, ou une seule)."""
    if capability is not None:
        return {capability: sorted(_REGISTRY.get(capability, {}).keys())}
    return {cap: sorted(keys.keys()) for cap, keys in _REGISTRY.items()}
