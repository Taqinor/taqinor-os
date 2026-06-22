"""Interfaces de fournisseurs IA + implémentations NO-OP.

Chaque capacité IA expose UNE interface (classe abstraite légère) et une
implémentation NO-OP qui est le DÉFAUT du registre. Le NO-OP :

  * ne fait aucun appel réseau,
  * n'importe ni n'exige aucune dépendance externe (clé/SDK),
  * ne coûte rien,
  * renvoie un :class:`AIResult` ``configured=False`` indiquant proprement que
    la capacité n'est pas active — l'appelant retombe sur la saisie manuelle.

Un vrai fournisseur (Zhipu vision pour l'OCR, faster-whisper pour le STT, Groq
pour le LLM…) se branche en sous-classant l'interface et en s'enregistrant via
``register_provider`` ; il ne devient ACTIF que lorsque ``settings.AI_PROVIDERS``
le sélectionne ET que sa configuration (clé) est présente. Sinon : NO-OP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIResult:
    """Résultat normalisé d'une capacité IA.

    ``configured`` = False signifie « aucun fournisseur actif » (chemin NO-OP) :
    l'appelant doit retomber sur le comportement manuel. ``ok`` = True signifie
    qu'un fournisseur a tourné sans erreur. ``data`` porte la charge utile
    (texte OCR, transcription, score QA…), ``error`` l'éventuel message.
    """

    ok: bool = False
    configured: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    provider: str = 'noop'

    @classmethod
    def noop(cls, provider: str = 'noop') -> 'AIResult':
        """Résultat NO-OP standard : aucun fournisseur configuré."""
        return cls(ok=False, configured=False, data={}, error=None, provider=provider)


class _BaseProvider:
    """Base commune : ``key`` identifie le fournisseur dans le registre."""

    key = 'base'
    label = 'Fournisseur'
    capability = 'base'

    def is_configured(self) -> bool:
        """Un fournisseur n'est ACTIF que s'il est configuré.

        Le NO-OP renvoie toujours False (jamais d'appel réel). Un vrai
        fournisseur surcharge pour vérifier la présence de sa clé/config.
        """
        return False


class OCRProvider(_BaseProvider):
    """Capacité : OCR d'un document (image/PDF) → champs structurés."""

    capability = 'ocr'

    def extract(self, *, content: bytes, mime_type: str, schema: str,
                hint: str | None = None) -> AIResult:
        """Extrait des champs depuis ``content`` selon ``schema``.

        ``schema`` nomme le gabarit attendu (ex. ``'cin'``, ``'contrat'``,
        ``'bon_livraison'``). Renvoie un :class:`AIResult` dont ``data`` porte
        les champs reconnus."""
        raise NotImplementedError


class STTProvider(_BaseProvider):
    """Capacité : transcription audio → texte (speech-to-text)."""

    capability = 'stt'

    def transcribe(self, *, content: bytes, mime_type: str,
                   language: str = 'fr') -> AIResult:
        """Transcrit ``content`` audio. ``data['text']`` porte la transcription."""
        raise NotImplementedError


class VisionQAProvider(_BaseProvider):
    """Capacité : contrôle qualité vision sur une photo d'installation."""

    capability = 'vision_qa'

    def inspect(self, *, content: bytes, mime_type: str,
                checklist: list[str]) -> AIResult:
        """Inspecte la photo selon ``checklist`` (alignement, étiquettes…).

        ``data`` doit porter ``score`` (0-100) et ``flags`` (liste de str)."""
        raise NotImplementedError


class LLMProvider(_BaseProvider):
    """Capacité : génération texte (synthèse, brouillon de réponse)."""

    capability = 'llm'

    def complete(self, *, prompt: str, system: str | None = None,
                 max_tokens: int = 512) -> AIResult:
        """Complète ``prompt``. ``data['text']`` porte la sortie générée."""
        raise NotImplementedError


# --- Implémentations NO-OP (le DÉFAUT — aucune dépendance, aucun coût) -------

class NoOpOCRProvider(OCRProvider):
    key = 'noop'
    label = 'Aucun OCR (saisie manuelle)'

    def extract(self, *, content, mime_type, schema, hint=None):  # noqa: D401
        return AIResult.noop(self.key)


class NoOpSTTProvider(STTProvider):
    key = 'noop'
    label = 'Aucune transcription (saisie manuelle)'

    def transcribe(self, *, content, mime_type, language='fr'):  # noqa: D401
        return AIResult.noop(self.key)


class NoOpVisionQAProvider(VisionQAProvider):
    key = 'noop'
    label = 'Aucun contrôle vision'

    def inspect(self, *, content, mime_type, checklist):  # noqa: D401
        return AIResult.noop(self.key)


class NoOpLLMProvider(LLMProvider):
    key = 'noop'
    label = 'Aucune génération (heuristique uniquement)'

    def complete(self, *, prompt, system=None, max_tokens=512):  # noqa: D401
        return AIResult.noop(self.key)
