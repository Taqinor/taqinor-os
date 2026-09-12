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

import functools
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Méthode « utile » de chaque capacité — celle qui déclenche un appel RÉEL et
#: donc une ligne de journal d'usage (NTAI1).
CAPABILITY_METHODS = ('extract', 'transcribe', 'inspect', 'complete')


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


def _instrumenter(methode):
    """Enveloppe une méthode de capacité : mesure + journal d'usage (NTAI1).

    Le chemin NO-OP (``key == 'noop'``) est laissé STRICTEMENT intact : aucun
    chronomètre, aucun journal — un fournisseur qui ne fait rien ne consomme
    rien. Pour un fournisseur RÉEL, l'appel est chronométré et une ligne
    best-effort est écrite (voir :mod:`core.ai.usage`) ; le journal ne peut ni
    modifier le résultat ni faire échouer l'appel.
    """

    @functools.wraps(methode)
    def _enveloppe(self, *args, **kwargs):
        if getattr(self, 'key', 'noop') == 'noop':
            return methode(self, *args, **kwargs)

        from core.ai.usage import record_usage, tokens_from_result

        debut = time.monotonic()
        try:
            resultat = methode(self, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — on journalise PUIS on relance
            try:
                record_usage(
                    capability=getattr(self, 'capability', 'llm'),
                    provider=getattr(self, 'key', 'noop'),
                    latency_ms=int((time.monotonic() - debut) * 1000),
                    success=False, error=str(exc))
            except Exception:  # noqa: BLE001 — le journal ne masque rien
                logger.warning('core.ai: usage non journalisé', exc_info=True)
            raise

        try:
            prompt_tokens, completion_tokens = tokens_from_result(resultat)
            record_usage(
                capability=getattr(self, 'capability', 'llm'),
                provider=getattr(self, 'key', 'noop'),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=int((time.monotonic() - debut) * 1000),
                success=bool(getattr(resultat, 'ok', False)),
                error=str(getattr(resultat, 'error', '') or ''))
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('core.ai: usage non journalisé', exc_info=True)
        return resultat

    _enveloppe.__ai_instrumente__ = True
    return _enveloppe


class _BaseProvider:
    """Base commune : ``key`` identifie le fournisseur dans le registre.

    NTAI1 — toute sous-classe (y compris un fournisseur tiers futur, ou un
    double de test) voit ses méthodes de capacité instrumentées AUTOMATIQUEMENT
    à la création de la classe : la mesure ne dépend donc pas de la discipline
    de l'auteur du fournisseur.
    """

    key = 'base'
    label = 'Fournisseur'
    capability = 'base'

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for nom in CAPABILITY_METHODS:
            methode = cls.__dict__.get(nom)
            if methode is None or not callable(methode):
                continue
            if getattr(methode, '__ai_instrumente__', False):
                continue  # déjà enveloppée (héritage d'une classe instrumentée)
            setattr(cls, nom, _instrumenter(methode))

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
