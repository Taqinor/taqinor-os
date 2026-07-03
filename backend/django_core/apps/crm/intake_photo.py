"""QK6 — Photo de facture/compteur/toiture captée par le site → pièce jointe lead.

Le site public peut joindre au payload du webhook une photo encodée en base64
(``photo`` / ``photoBase64``, éventuellement en data-URL). Ici on :

1. décode et VALIDE la photo (mêmes gardes magic-bytes/10 Mo que le stockage
   générique des pièces jointes — ``apps.records.storage``, app fondation) ;
2. l'attache au lead via le modèle générique ``records.Attachment`` (company
   TOUJOURS celle du lead — jamais lue du payload — multi-tenant) ;
3. si l'OCR de capture est activé (``CRM_CAPTURE_OCR_ENABLED``, KEY-GATED :
   OFF par défaut), envoie la photo au service FastAPI IA existant
   (Zhipu OCR, ``/ocr/process_document``) et récupère tranche/consommation
   pour pré-remplir le lead — UNIQUEMENT les champs encore vides.

DÉGRADATION DOUCE : sans clé/flag, la photo reste une simple pièce jointe ;
aucune erreur ne remonte jamais au webhook (le lead prime sur la photo).
"""

import base64
import binascii
import logging
import os
import re

from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# ~10 Mo décodés (la limite dure est ré-appliquée par records.storage).
_MAX_B64_CHARS = 14 * 1024 * 1024
_OCR_TIMEOUT = 30  # s — jamais bloquer le webhook indéfiniment

# Clés tolérées pour la photo (camelCase + snake_case, comme le reste du webhook).
_PHOTO_KEYS = ('photo', 'photoBase64', 'photo_base64',
               'meterPhoto', 'meter_photo', 'billPhoto', 'bill_photo')
_FILENAME_KEYS = ('photoFilename', 'photo_filename')


def capture_ocr_enabled() -> bool:
    """QK6 — True si l'OCR de capture est activé (flag + clé côté founder).

    KEY-GATED : sans ``CRM_CAPTURE_OCR_ENABLED``, aucune requête réseau,
    aucun coût — la photo est simplement jointe au lead."""
    return bool(getattr(settings, 'CRM_CAPTURE_OCR_ENABLED', False))


def _fastapi_ocr_url() -> str:
    """URL interne de l'endpoint OCR FastAPI (même convention que chat.tasks)."""
    base = (getattr(settings, 'FASTAPI_INTERNAL_URL', '')
            or os.environ.get('FASTAPI_INTERNAL_URL', '')
            or 'http://fastapi_ia:8001/api/fastapi')
    return base.rstrip('/') + '/ocr/process_document'


def _service_token_for(user) -> str:
    """Jeton JWT court pour relayer l'auth vers FastAPI (même SECRET_KEY/HS256
    que ``verify_token`` côté service). Sans utilisateur exploitable : ''."""
    if user is None:
        return ''
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        return str(AccessToken.for_user(user))
    except Exception:  # pragma: no cover — défensif
        return ''


def _decode_photo(data: dict):
    """Extrait et décode la photo du payload. Retourne (octets, nom) ou (None, '').

    Tolérant : accepte une data-URL (``data:image/jpeg;base64,...``) ou du
    base64 nu ; toute valeur invalide → (None, '') sans jamais lever."""
    raw = None
    for key in _PHOTO_KEYS:
        candidate = data.get(key)
        if isinstance(candidate, str) and candidate.strip():
            raw = candidate.strip()
            break
    if not raw or len(raw) > _MAX_B64_CHARS:
        return None, ''
    # data-URL → ne garder que la charge base64.
    if raw.startswith('data:'):
        _, _, raw = raw.partition(',')
        if not raw:
            return None, ''
    try:
        content = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None, ''
    if not content:
        return None, ''
    filename = ''
    for key in _FILENAME_KEYS:
        candidate = data.get(key)
        if isinstance(candidate, str) and candidate.strip():
            filename = candidate.strip()[:255]
            break
    return content, filename or 'photo-capture.jpg'


def attach_capture_photo(lead, data: dict):
    """Attache la photo du payload au lead (+ OCR si configuré). Best-effort.

    Retourne l'Attachment créé, ou None (photo absente/invalide/refusée).
    Ne lève JAMAIS — la création du lead prime toujours sur la photo."""
    try:
        content, filename = _decode_photo(data or {})
        if content is None:
            return None

        # Stockage générique (validation magic-bytes + 10 Mo + MinIO) — app
        # fondation `records`, réutilisée telle quelle (aucun nouveau chemin).
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Attachment
        from apps.records.storage import store_attachment

        from .models import Lead, LeadActivity

        meta, err = store_attachment(ContentFile(content, name=filename))
        if err:
            logger.info(
                'attach_capture_photo: photo refusée (lead #%s) : %s',
                lead.pk, err)
            return None

        attachment = Attachment.objects.create(
            # Multi-tenant : company du LEAD, jamais du payload.
            company=lead.company,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=lead.pk,
            uploaded_by=None,
            **meta,
        )
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body='Photo de facture/compteur jointe via le site web',
        )

        # OCR key-gated : sans flag/clé → simple pièce jointe (dégradation douce).
        if capture_ocr_enabled():
            _run_capture_ocr(lead, content, filename, meta.get('mime', ''))
        return attachment
    except Exception as exc:  # noqa: BLE001 — jamais bloquer le webhook
        logger.warning(
            'attach_capture_photo: échec (lead #%s) : %s',
            getattr(lead, 'pk', None), exc)
        return None


def _run_capture_ocr(lead, content: bytes, filename: str, mime: str) -> None:
    """Envoie la photo à l'OCR FastAPI (Zhipu) et pré-remplit tranche/conso.

    N'écrase JAMAIS une valeur déjà présente sur le lead. Best-effort : toute
    panne (pas de owner → pas de jeton, réseau, réponse inattendue) est
    silencieuse — la photo reste jointe quoi qu'il arrive."""
    try:
        token = _service_token_for(getattr(lead, 'owner', None))
        if not token:
            logger.info(
                'capture OCR: pas d\'utilisateur pour le jeton (lead #%s) — '
                'photo jointe sans OCR', lead.pk)
            return

        import requests

        resp = requests.post(
            _fastapi_ocr_url(),
            files={'file': (filename, content, mime or 'image/jpeg')},
            headers={'Authorization': f'Bearer {token}'},
            timeout=_OCR_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.info('capture OCR: statut %s (lead #%s)',
                        resp.status_code, lead.pk)
            return
        payload = resp.json() or {}
        structurees = payload.get('donnees_structurees') or {}
        texte = payload.get('texte_brut') or ''

        updates = []
        conso = _extract_conso_kwh(structurees, texte)
        if conso is not None and lead.conso_mensuelle_kwh in (None, ''):
            lead.conso_mensuelle_kwh = conso
            updates.append('conso_mensuelle_kwh')
        tranche = _extract_tranche(structurees, texte)
        if tranche and not lead.tranche_onee:
            lead.tranche_onee = tranche[:100]
            updates.append('tranche_onee')
        if updates:
            lead.save(update_fields=updates)
            from .models import LeadActivity
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body='OCR de la photo : ' + ', '.join(
                    'consommation ≈ %s kWh/mois' % lead.conso_mensuelle_kwh
                    if f == 'conso_mensuelle_kwh'
                    else 'tranche « %s »' % lead.tranche_onee
                    for f in updates),
            )
    except Exception as exc:  # noqa: BLE001 — l'OCR ne casse jamais la capture
        logger.info('capture OCR: échec silencieux (lead #%s) : %s',
                    getattr(lead, 'pk', None), exc)


def _extract_conso_kwh(structurees: dict, texte: str):
    """Consommation mensuelle (kWh) depuis les données structurées OCR, sinon
    premier motif « N kWh » plausible du texte brut. None si introuvable."""
    for key in ('conso_kwh', 'consommation_kwh', 'consommation', 'kwh'):
        val = structurees.get(key)
        if val in (None, ''):
            continue
        try:
            num = float(str(val).replace(' ', '').replace(',', '.'))
        except (TypeError, ValueError):
            continue
        if 0 < num < 1_000_000:
            return num
    match = re.search(r'(\d[\d\s]{0,8}(?:[.,]\d{1,2})?)\s*k\s*[wW]\s*h',
                      texte or '')
    if match:
        try:
            num = float(match.group(1).replace(' ', '').replace(',', '.'))
        except (TypeError, ValueError):
            return None
        if 0 < num < 1_000_000:
            return num
    return None


def _extract_tranche(structurees: dict, texte: str):
    """Tranche tarifaire depuis les données structurées, sinon le motif
    « tranche … » du texte brut. Chaîne courte, ou None."""
    for key in ('tranche', 'tranche_onee'):
        val = structurees.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)):
            return str(val)
    match = re.search(r'[Tt]ranche\s*[:\-]?\s*([^\n;,]{1,60})', texte or '')
    if match:
        cleaned = match.group(1).strip()
        return cleaned or None
    return None
