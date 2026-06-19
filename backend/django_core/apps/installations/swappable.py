"""Interfaces SWAPPABLES du module d'exécution terrain (F9 / F14 / F20).

Trois capacités optionnelles — extraction de n° de série (OCR, F9),
transcription de mémo vocal (F14) et contrôle qualité IA des photos (F20) —
sont conçues exactement sur le patron de l'OCR factures : elles n'ajoutent
AUCUN identifiant externe et AUCUN coût par défaut, et NO-OP en toute sécurité
tant qu'aucun fournisseur n'est explicitement configuré dans Paramètres.

Le fournisseur se choisit par société dans CompanyProfile (champs
`ocr_serie_provider`, `transcription_provider`, `photo_qa_provider`). Tant que
le champ vaut '' (défaut), l'appel renvoie un résultat NEUTRE :

  * OCR série      → None (on garde le champ saisi à la main) ;
  * transcription  → le libellé « Non transcrit — service non configuré » ;
  * QA photo       → liste vide (aucun signalement), jamais bloquant.

Aucune des trois ne lève jamais : un échec fournisseur retombe sur le neutre.
Aucune dépendance pip nouvelle n'est introduite ici.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Libellé NEUTRE d'un mémo vocal non transcrit (F14). Source de vérité unique.
TRANSCRIPTION_NON_CONFIGUREE = 'Non transcrit — service non configuré'


def _provider(company, field):
    """Fournisseur configuré pour la société sur `field`, ou '' (= no-op)."""
    if company is None:
        return ''
    try:
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company)
        return (getattr(prof, field, '') or '').strip()
    except Exception:  # pragma: no cover - défensif
        return ''


# ── F9 — extraction OCR d'un numéro de série depuis la photo de la plaque ─────
def extract_serial(company, image_bytes):
    """Extrait un n° de série depuis l'image d'une plaque signalétique.

    NO-OP par défaut : renvoie None tant qu'aucun fournisseur OCR n'est
    configuré (`CompanyProfile.ocr_serie_provider`). On RETOMBE toujours sur la
    saisie manuelle — l'absence d'extraction ne bloque jamais. Ne lève jamais.
    """
    provider = _provider(company, 'ocr_serie_provider')
    if not provider:
        return None
    # Aucun fournisseur n'est branché aujourd'hui (décision opérateur, hors de
    # ce module). Le jour où l'un l'est, son adaptateur se brancherait ici.
    logger.info('OCR série : fournisseur « %s » non implémenté — no-op.',
                provider)
    return None


def serial_ocr_active(company):
    """True si un fournisseur OCR de série est configuré pour la société."""
    return bool(_provider(company, 'ocr_serie_provider'))


# ── F14 — transcription d'un mémo vocal ───────────────────────────────────────
def transcribe(company, audio_bytes):
    """Transcrit un mémo vocal (Darija + français).

    NO-OP par défaut : renvoie (texte, configure) où `configure` est False et
    `texte` = TRANSCRIPTION_NON_CONFIGUREE tant qu'aucun fournisseur n'est
    configuré (`CompanyProfile.transcription_provider`). L'audio d'origine
    reste la source de vérité ; le transcript reste éditable. Ne lève jamais.
    """
    provider = _provider(company, 'transcription_provider')
    if not provider:
        return TRANSCRIPTION_NON_CONFIGUREE, False
    logger.info('Transcription : fournisseur « %s » non implémenté — no-op.',
                provider)
    return TRANSCRIPTION_NON_CONFIGUREE, False


def transcription_active(company):
    """True si un fournisseur de transcription est configuré pour la société."""
    return bool(_provider(company, 'transcription_provider'))


# ── F20 — contrôle qualité IA des photos obligatoires ─────────────────────────
def photo_qa_active(company):
    """True si un fournisseur de QA photo IA est configuré pour la société."""
    return bool(_provider(company, 'photo_qa_provider'))


def review_photos(company, photos):
    """Signale les photos obligatoires probablement manquantes/de mauvaise
    qualité. NO-OP par défaut : renvoie [] tant qu'aucun fournisseur de vision
    n'est configuré (`CompanyProfile.photo_qa_provider`). Ne bloque JAMAIS la
    complétion, ne lève jamais. `photos` = liste de dicts décrivant les prises.
    """
    provider = _provider(company, 'photo_qa_provider')
    if not provider:
        return []
    logger.info('QA photo : fournisseur « %s » non implémenté — no-op.',
                provider)
    return []
