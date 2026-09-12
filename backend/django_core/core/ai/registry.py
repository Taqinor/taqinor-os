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
    BudgetExhaustedLLMProvider,
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


def _budget_epuise() -> bool:
    """NTAI2 — True si la société du contexte a dépassé son plafond IA.

    Sans contexte de société (appel hors requête, tâche sans société) ou sans
    budget défini, renvoie False : on ne bride JAMAIS sur une société devinée.
    Ne lève jamais — ``budget_status`` encapsule déjà ses propres erreurs."""
    from core.ai.usage import budget_status, current_context

    company_id = current_context().company_id
    if company_id is None:
        return False
    return bool(budget_status(company_id).depasse)


def get_provider(capability: str):
    """Retourne une INSTANCE du fournisseur sélectionné pour ``capability``.

    Sélectionne selon ``settings.AI_PROVIDERS`` ; retombe sur le NO-OP si la
    capacité ou la clé est inconnue. De plus, si le fournisseur sélectionné
    n'est PAS configuré (clé absente), on retombe AUSSI sur le NO-OP — garantie
    « aucun appel sans config ».

    NTAI2 — COUPE-CIRCUIT : au-delà de 100 % du budget IA mensuel de la société
    courante, la capacité ``llm`` rend un NO-OP « budget épuisé » (même chemin
    de dégradation qu'une clé absente, jamais une exception)."""
    if capability not in _CAPABILITY_BASE:
        raise ValueError(f"Capacité IA inconnue : {capability!r}")
    providers = _REGISTRY.get(capability, {})
    key = _selected_key(capability)
    cls = providers.get(key) or _NOOP[capability]
    instance = cls()
    # Garde-fou : un fournisseur sélectionné mais non configuré → NO-OP.
    if key != 'noop' and not instance.is_configured():
        return _NOOP[capability]()
    if capability == 'llm' and key != 'noop' and _budget_epuise():
        return BudgetExhaustedLLMProvider()
    return instance


def is_capability_configured(capability: str) -> bool:
    """True si un fournisseur RÉEL (non NO-OP) est actif pour ``capability``."""
    provider = get_provider(capability)
    return getattr(provider, 'key', 'noop') != 'noop'


def capabilities_status(company=None) -> list:
    """NTAI6 — État RÉEL de chaque capacité IA pour une société.

    Pour chaque capacité : le fournisseur sélectionné, s'il est réellement
    configuré, POURQUOI il ne l'est pas le cas échéant, et — quand le journal
    d'usage a des lignes (NTAI1) — le nombre d'appels, la latence médiane et la
    dernière erreur rapportée.

    AUCUN SECRET n'est exposé : on renvoie la CLÉ du fournisseur (« groq »),
    jamais sa clé d'API. Sans société ou sans mesure, les champs de mesure
    valent ``None`` — « pas de mesure » et « zéro appel » ne se confondent
    pas."""
    from core.ai.usage import capability_metrics

    mesures = capability_metrics(company) if company is not None else {}
    etat = []
    for capability in sorted(_CAPABILITY_BASE):
        choisi = _selected_key(capability)
        provider = get_provider(capability)
        actif = getattr(provider, 'key', 'noop')
        configure = actif != 'noop'
        if configure:
            motif = ''
        elif getattr(provider, 'raison', '') == 'budget_epuise':
            # Le fournisseur EST configuré : c'est le budget qui l'a mis en
            # veille (NTAI2). Le dire, plutôt que « aucun fournisseur ».
            motif = ('Budget IA du mois épuisé — génération suspendue '
                     'jusqu\'au relèvement du plafond.')
        elif choisi == 'noop':
            motif = 'Aucun fournisseur sélectionné pour cette capacité.'
        elif choisi not in _REGISTRY.get(capability, {}):
            motif = f'Fournisseur « {choisi} » inconnu du registre.'
        else:
            motif = (f'Fournisseur « {choisi} » sélectionné mais non '
                     'configuré (clé absente).')
        mesure = mesures.get(capability) or {}
        etat.append({
            'capacite': capability,
            'fournisseur_choisi': choisi,
            'fournisseur_actif': actif,
            'label': getattr(provider, 'label', ''),
            'configure': configure,
            'motif': motif,
            'appels': mesure.get('appels'),
            'latence_p50_ms': mesure.get('latence_p50_ms'),
            'derniere_erreur': mesure.get('derniere_erreur'),
            'derniere_erreur_le': mesure.get('derniere_erreur_le'),
        })
    return etat


def available_providers(capability: str | None = None) -> dict:
    """Liste les clés enregistrées (toutes capacités, ou une seule)."""
    if capability is not None:
        return {capability: sorted(_REGISTRY.get(capability, {}).keys())}
    return {cap: sorted(keys.keys()) for cap, keys in _REGISTRY.items()}
