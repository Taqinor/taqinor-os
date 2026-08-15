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

import json
import logging
import re
import unicodedata

from core.ai.registry import get_provider, is_capability_configured

logger = logging.getLogger(__name__)


class AnalyseIndisponible(Exception):
    """Analyse impossible : ``configured=False`` → pas de clé LLM (503 douce)."""

    def __init__(self, message, *, configured=True):
        super().__init__(message)
        self.configured = configured


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


# ─────────────────────────────────────────────────────────────────────────────
# NTAI22 — Objections / next-steps / sentiment d'un appel
# ─────────────────────────────────────────────────────────────────────────────
#
# GARDE ANTI-HALLUCINATION (NTAI4) : un LLM invite volontiers une objection
# plausible que le client n'a jamais formulée. Ici, tout élément extrait doit
# être ANCRÉ dans le transcript — au moins un mot significatif de l'élément doit
# s'y trouver réellement. Ce qui n'est pas ancré est ÉCARTÉ (jamais rendu), et
# le sentiment est ramené à une valeur fermée. On préfère une analyse pauvre à
# une analyse inventée.

#: Sentiments autorisés — toute autre valeur est ramenée à « neutre ».
SENTIMENTS = ('positif', 'neutre', 'negatif')

ANALYSE_APPEL_SYSTEM = (
    "Tu analyses la transcription d'un appel commercial (installateur solaire "
    'au Maroc). Réponds UNIQUEMENT par un objet JSON avec les clés : '
    '"objections" (liste de phrases courtes RÉELLEMENT dites par le client), '
    '"next_steps" (liste des engagements pris pendant l\'appel), '
    '"produits" (liste des produits/équipements mentionnés), '
    '"sentiment" ("positif", "neutre" ou "negatif"). '
    "N'invente RIEN : si une information n'est pas dans la transcription, "
    'laisse la liste vide. Ne déduis aucun prix, aucun délai, aucune remise.'
)

#: Mots trop courants pour ancrer quoi que ce soit (un « le » partagé ne prouve
#: pas qu'une objection a été formulée).
_MOTS_VIDES = {
    'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou', 'que',
    'qui', 'est', 'pas', 'pour', 'avec', 'sur', 'dans', 'client', 'appel',
    'nous', 'vous', 'ils', 'elle', 'son', 'sa', 'ses', 'ce', 'cette', 'plus',
    'trop', 'tres', 'trop', 'mais', 'donc', 'par', 'en', 'au', 'aux',
}

_MOT_RE = re.compile(r"[\w']{3,}", re.UNICODE)


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize('NFKD', texte or '')
    return ''.join(c for c in decompose if not unicodedata.combining(c))


def _mots_significatifs(texte: str) -> set:
    mots = _MOT_RE.findall(_sans_accents(str(texte or '')).lower())
    return {m for m in mots if m not in _MOTS_VIDES}


def ancre_dans_transcript(element: str, transcript: str) -> bool:
    """NTAI4 — True si ``element`` s'appuie sur des mots RÉELS du transcript.

    Un élément dont aucun mot significatif n'apparaît dans le transcript est
    considéré comme inventé et sera écarté.
    """
    mots = _mots_significatifs(element)
    if not mots:
        return False
    return bool(mots & _mots_significatifs(transcript))


def _liste_ancree(valeurs, transcript, *, limite=10):
    """Nettoie une liste extraite : chaînes non vides, ANCRÉES, dédupliquées."""
    if not isinstance(valeurs, (list, tuple)):
        return []
    sortie = []
    for valeur in valeurs:
        texte = str(valeur or '').strip()
        if not texte or texte in sortie:
            continue
        if not ancre_dans_transcript(texte, transcript):
            continue
        sortie.append(texte[:300])
        if len(sortie) >= limite:
            break
    return sortie


def _parse_analyse(texte: str, transcript: str) -> dict:
    """Extrait l'analyse structurée d'une sortie LLM (JSON éventuellement noyé).

    Ne lève jamais et n'invente jamais : sans JSON exploitable, toutes les
    listes sont vides et le sentiment vaut « neutre ».
    """
    charge = None
    match = re.search(r'\{.*\}', str(texte or ''), re.DOTALL)
    if match:
        try:
            charge = json.loads(match.group(0))
        except (ValueError, TypeError):
            charge = None
    if not isinstance(charge, dict):
        charge = {}
    sentiment = str(charge.get('sentiment') or '').strip().lower()
    return {
        'objections': _liste_ancree(charge.get('objections'), transcript),
        'next_steps': _liste_ancree(charge.get('next_steps'), transcript),
        'produits': _liste_ancree(charge.get('produits'), transcript),
        'sentiment': sentiment if sentiment in SENTIMENTS else 'neutre',
    }


def analyser_appel(appel, *, max_tokens=500) -> dict:
    """NTAI22 — Extrait objections / next-steps / produits / sentiment.

    Lève :class:`AnalyseIndisponible` sans transcript (400) ou sans clé LLM
    (503 douce, aucun appel réseau). Persiste l'analyse sur l'appel pour que
    l'agrégation de coaching n'ait jamais à rappeler le LLM.

    N'ÉCRIT RIEN dans le CRM : les relances sont PROPOSÉES, et créées seulement
    par un appel de confirmation explicite (:func:`confirmer_relances`).
    """
    from django.utils import timezone

    transcript = (appel.transcript or '').strip()
    if not transcript:
        raise AnalyseIndisponible(
            "Cet appel n'a pas encore de transcription à analyser.")
    if not is_capability_configured('llm'):
        raise AnalyseIndisponible(
            "Analyse d'appel indisponible : aucune clé LLM configurée.",
            configured=False)

    res = get_provider('llm').complete(
        prompt=f'Transcription :\n{transcript[:12000]}',
        system=ANALYSE_APPEL_SYSTEM, max_tokens=max_tokens)
    if not res.ok:
        raise AnalyseIndisponible(
            res.error or "Le fournisseur n'a pas produit d'analyse.")

    analyse = _parse_analyse((res.data or {}).get('text'), transcript)
    appel.analyse_json = analyse
    appel.sentiment = analyse['sentiment']
    appel.analyse_le = timezone.now()
    appel.save(update_fields=[
        'analyse_json', 'sentiment', 'analyse_le', 'updated_at'])
    return analyse


def proposer_relances(appel, analyse) -> list:
    """NTAI22 — Propose (SANS RIEN ÉCRIRE) une relance par next-step.

    Renvoie ``[{'resume': ..., 'delai_jours': 3}]``. Liste vide quand l'appel
    n'est rattaché à aucun lead : proposer une relance sans destinataire n'a
    aucun sens.
    """
    if not appel.lead_id:
        return []
    return [
        {'resume': etape[:255], 'delai_jours': 3}
        for etape in (analyse or {}).get('next_steps', [])
    ]


def confirmer_relances(appel, relances, *, user=None) -> list:
    """NTAI22 — CRÉE les relances confirmées par l'utilisateur.

    Écrit des ``records.Activity`` (le socle d'activités générique — une app de
    FONDATION) sur le lead, désigné par ``ContentType`` NATUREL (``crm.lead``) :
    aucun modèle d'une app métier n'est importé ici.

    Seules des relances EXPLICITEMENT envoyées sont créées : rien n'est écrit
    par le simple fait d'avoir analysé l'appel.
    """
    from datetime import timedelta

    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone

    from apps.records.models import Activity

    if not appel.lead_id or not relances:
        return []
    content_type = ContentType.objects.get_by_natural_key('crm', 'lead')
    aujourdhui = timezone.now().date()
    creees = []
    for relance in relances:
        if not isinstance(relance, dict):
            continue
        resume = str(relance.get('resume') or '').strip()
        if not resume:
            continue
        try:
            delai = int(relance.get('delai_jours') or 3)
        except (TypeError, ValueError):
            delai = 3
        creees.append(Activity.objects.create(
            company_id=appel.company_id,
            content_type=content_type, object_id=appel.lead_id,
            summary=resume[:255],
            due_date=aujourdhui + timedelta(days=max(delai, 0)),
            assigned_to=user if getattr(user, 'pk', None) else None,
            created_by=user if getattr(user, 'pk', None) else None,
            note=f'[appel:{appel.pk}] relance proposée par analyse IA'))
    return creees
