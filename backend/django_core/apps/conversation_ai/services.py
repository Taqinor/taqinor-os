"""Services du module « conversation_ai » (Groupe NTAI).

Trois invariants, identiques au reste de la couche IA du dépôt :

  1. **Key-gated** — sans fournisseur STT configuré (``core.ai`` retombe sur le
     NO-OP), la transcription ne fait AUCUN appel réseau et laisse l'appel au
     statut ``non_transcrit``. Jamais une erreur, jamais un coût.
  2. **Best-effort, jamais bloquant** — un échec est capturé dans l'appel
     (``statut='erreur'`` + ``message``) ; les services ne lèvent pas.
  3. **Aucune écriture métier implicite** — ce module stocke un transcript ;
     il n'écrit jamais dans le CRM sans une confirmation humaine explicite.
"""
from __future__ import annotations

import logging

from core.ai.registry import is_capability_configured

logger = logging.getLogger(__name__)

#: Taille (octets) au-delà de laquelle l'audio est découpé avant transcription.
#: Beaucoup de fournisseurs STT plafonnent la taille d'une requête ; un appel
#: d'une heure la dépasse.
SEGMENT_MAX_BYTES = 20 * 1024 * 1024


class AppelUploadError(Exception):
    """Téléversement refusé (format non supporté, fichier trop lourd…)."""


def stt_configure() -> bool:
    """True si un fournisseur STT RÉEL est actif (jamais le NO-OP)."""
    return is_capability_configured('stt')


def stocker_audio(fichier, *, company):
    """Téléverse l'enregistrement dans le stockage objet partagé.

    Réutilise ``records.storage.store_attachment`` (validation de format audio,
    limite de taille, clé PRÉFIXÉE PAR LA SOCIÉTÉ — SCA42) : aucun second
    pipeline d'upload n'est créé ici. Lève :class:`AppelUploadError` si le
    stockage refuse le fichier.
    """
    from apps.records.storage import store_attachment

    infos, erreur = store_attachment(fichier, audio=True, company=company)
    if erreur:
        raise AppelUploadError(erreur)
    return infos


def decouper_audio(content: bytes, mime: str) -> list:
    """Découpe l'audio en segments transcriptibles (un seul par défaut).

    Un découpage AUDIO correct (sur les frontières de trames) exige une
    bibliothèque de décodage — une dépendance externe qui reste une décision
    du fondateur. Tant qu'aucun découpeur n'est branché, on renvoie l'audio
    ENTIER : le fournisseur STT reçoit ce qu'il aurait reçu de toute façon, et
    la boucle de segmentation ci-dessous (réelle et testée) accueillera un vrai
    découpeur sans changer le reste du flux.
    """
    if not content:
        return []
    return [content]


def transcrire_appel(appel) -> bool:
    """NTAI21 — Transcrit l'enregistrement d'un appel (best-effort).

    Renvoie True si un transcript a été posé. Sans fournisseur STT actif :
    laisse l'appel ``non_transcrit``, ne lit MÊME PAS les octets du stockage
    (aucun appel réseau) et renvoie False — sans lever.
    """
    from django.utils import timezone

    from .models import AppelCommercial

    if not stt_configure():
        return False
    if not appel.fichier_key:
        return False

    appel.statut = AppelCommercial.STATUT_EN_COURS
    appel.save(update_fields=['statut', 'updated_at'])

    try:
        from apps.records.storage import fetch_attachment
        from core.ai.services import transcribe_audio

        contenu, erreur = fetch_attachment(appel.fichier_key)
        if not contenu:
            raise RuntimeError(erreur or 'Enregistrement introuvable.')

        morceaux = []
        for segment in decouper_audio(contenu, appel.mime):
            res = transcribe_audio(
                content=segment, mime_type=appel.mime or 'audio/mpeg',
                language='fr')
            if not res.ok:
                if res.error:
                    raise RuntimeError(res.error)
                continue
            texte = str((res.data or {}).get('text') or '').strip()
            if texte:
                morceaux.append(texte)

        appel.transcript = '\n'.join(morceaux)
        appel.statut = (AppelCommercial.STATUT_TRANSCRIT if morceaux
                        else AppelCommercial.STATUT_NON_TRANSCRIT)
        appel.message = ''
    except Exception as exc:  # noqa: BLE001 - best-effort, jamais bloquant.
        logger.warning('conversation_ai: transcription en échec (appel %s)',
                       appel.pk, exc_info=True)
        appel.statut = AppelCommercial.STATUT_ERREUR
        appel.message = str(exc)[:500]
    appel.transcrit_le = timezone.now()
    appel.save(update_fields=[
        'transcript', 'statut', 'message', 'transcrit_le', 'updated_at'])
    return appel.statut == AppelCommercial.STATUT_TRANSCRIT
