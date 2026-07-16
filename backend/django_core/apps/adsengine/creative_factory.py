"""ENG17 — Fabrique créative : adaptateurs key-gated (submit / poll / store).

Cinq fournisseurs, chacun activé UNIQUEMENT par sa clé d'environnement :
  * ``ZAPCAP_API_KEY``    — sous-titrage de reels ;
  * ``FAL_API_KEY``       — B-roll / statiques génératifs ;
  * ``TEMPLATED_API_KEY`` — stamps de marque ;
  * ``ELEVENLABS_API_KEY``— voix FR / darija ;
  * ``JSON2VIDEO_API_KEY``— assemblage d'explainers.

Contrat commun (méthode template ``run``) : ``submit`` → ``poll`` →
``store``→MinIO → ``CreativeAsset`` en **stamp policy PENDING** (jamais validé
automatiquement — la check-list humaine ENG16 reste obligatoire avant toute
diffusion). **NO-OP propre sans la clé** (``run`` renvoie ``None``, aucun appel
réseau). **Aucune dépendance pip nouvelle** : ``httpx`` (déjà épinglé) suffit ;
le stockage réutilise le client MinIO existant.
"""
from __future__ import annotations

import io
import logging
import os
import uuid

import httpx
from django.conf import settings

from .models import CreativeAsset

logger = logging.getLogger(__name__)


def _store_bytes(company, data, *, ext, content_type):
    """Dépose des octets dans MinIO sous une clé préfixée société et renvoie la
    clé (``adsengine/{company_id}/{uuid}.ext``). Réutilise le client MinIO
    existant — aucune dépendance nouvelle."""
    from apps.ventes.utils.minio_client import (
        ensure_uploads_bucket, get_minio_client,
    )

    cid = getattr(company, 'id', company) or 0
    safe_ext = (ext or 'bin').lstrip('.') or 'bin'
    key = f'adsengine/{cid}/{uuid.uuid4().hex}.{safe_ext}'
    client = get_minio_client()
    ensure_uploads_bucket()
    buf = data if hasattr(data, 'read') else io.BytesIO(data)
    client.upload_fileobj(
        buf, settings.MINIO_BUCKET_UPLOADS, key,
        ExtraArgs={'ContentType': content_type})
    return key


class CreativeFactoryAdapter:
    """Contrat commun d'un adaptateur de fabrique créative.

    Sous-classes : définissent ``env_key`` / ``source_lane`` / ``default_*`` et
    implémentent ``submit`` (lance un job, renvoie un id) + ``poll`` (attend et
    renvoie les OCTETS du média). ``run`` orchestre le tout et no-ope sans clé.
    """

    env_key = ''
    source_lane = ''
    default_asset_type = CreativeAsset.AssetType.STATIC
    default_ext = 'bin'
    default_content_type = 'application/octet-stream'
    base_url = ''

    def is_enabled(self):
        """Vrai si la clé d'environnement du fournisseur est présente."""
        return bool(os.environ.get(self.env_key))

    def _api_key(self):
        return os.environ.get(self.env_key, '')

    def _headers(self):
        return {'Authorization': f'Bearer {self._api_key()}'}

    def submit(self, client, payload):  # pragma: no cover - overridé
        raise NotImplementedError

    def poll(self, client, job_id):  # pragma: no cover - overridé
        raise NotImplementedError

    def run(self, company, payload=None, *, http_client=None, parent=None):
        """Orchestration submit→poll→store→CreativeAsset (pending).

        NO-OP (renvoie ``None``) si la clé est absente : aucun réseau, aucun
        asset. L'asset créé porte un ``policy_stamp`` VIDE (pending) : il ne peut
        pas être diffusé tant que la check-list humaine (ENG16) ne l'a pas validé.
        """
        if not self.is_enabled():
            logger.info(
                'creative_factory: %s désactivé (clé %s absente) — no-op',
                self.source_lane, self.env_key)
            return None
        payload = payload or {}
        client = http_client or httpx.Client(timeout=60.0)
        owns = http_client is None
        try:
            job_id = self.submit(client, payload)
            data = self.poll(client, job_id)
        finally:
            if owns:
                client.close()
        if not data:
            return None
        ext = payload.get('ext') or self.default_ext
        file_key = _store_bytes(
            company, data, ext=ext, content_type=self.default_content_type)
        return CreativeAsset.objects.create(
            company=company,
            asset_type=payload.get('asset_type', self.default_asset_type),
            file_key=file_key, source_lane=self.source_lane,
            cost_cents=int(payload.get('cost_cents') or 0),
            policy_stamp={},  # PENDING — jamais validé automatiquement
            parent=parent)


class ZapcapAdapter(CreativeFactoryAdapter):
    """Sous-titrage de reels (ZapCap)."""

    env_key = 'ZAPCAP_API_KEY'
    source_lane = 'zapcap'
    default_asset_type = CreativeAsset.AssetType.REEL
    default_ext = 'mp4'
    default_content_type = 'video/mp4'
    base_url = 'https://api.zapcap.ai'

    def submit(self, client, payload):
        resp = client.post(
            f'{self.base_url}/videos', json=payload.get('input', {}),
            headers={'x-api-key': self._api_key()})
        resp.raise_for_status()
        return resp.json().get('taskId') or resp.json().get('id')

    def poll(self, client, job_id):
        resp = client.get(
            f'{self.base_url}/videos/{job_id}',
            headers={'x-api-key': self._api_key()})
        resp.raise_for_status()
        url = resp.json().get('downloadUrl')
        return client.get(url).content if url else None


class FalAdapter(CreativeFactoryAdapter):
    """B-roll / statiques génératifs (fal.ai)."""

    env_key = 'FAL_API_KEY'
    source_lane = 'fal'
    default_asset_type = CreativeAsset.AssetType.STATIC
    default_ext = 'png'
    default_content_type = 'image/png'
    base_url = 'https://queue.fal.run'

    def _headers(self):
        return {'Authorization': f'Key {self._api_key()}'}

    def submit(self, client, payload):
        resp = client.post(
            f'{self.base_url}/{payload.get("model", "fal-ai/flux/dev")}',
            json=payload.get('input', {}), headers=self._headers())
        resp.raise_for_status()
        return resp.json().get('request_id') or resp.json().get('id')

    def poll(self, client, job_id):
        resp = client.get(
            f'{self.base_url}/requests/{job_id}', headers=self._headers())
        resp.raise_for_status()
        images = resp.json().get('images') or []
        url = images[0].get('url') if images else None
        return client.get(url).content if url else None


class TemplatedAdapter(CreativeFactoryAdapter):
    """Stamps de marque (Templated.io)."""

    env_key = 'TEMPLATED_API_KEY'
    source_lane = 'templated'
    default_asset_type = CreativeAsset.AssetType.STATIC
    default_ext = 'png'
    default_content_type = 'image/png'
    base_url = 'https://api.templated.io/v1'

    def submit(self, client, payload):
        resp = client.post(
            f'{self.base_url}/render', json=payload.get('input', {}),
            headers=self._headers())
        resp.raise_for_status()
        return resp.json().get('id')

    def poll(self, client, job_id):
        resp = client.get(
            f'{self.base_url}/render/{job_id}', headers=self._headers())
        resp.raise_for_status()
        url = resp.json().get('url')
        return client.get(url).content if url else None


class ElevenlabsAdapter(CreativeFactoryAdapter):
    """Voix FR / darija (ElevenLabs) — composant audio d'un explainer."""

    env_key = 'ELEVENLABS_API_KEY'
    source_lane = 'elevenlabs'
    default_asset_type = CreativeAsset.AssetType.EXPLAINER
    default_ext = 'mp3'
    default_content_type = 'audio/mpeg'
    base_url = 'https://api.elevenlabs.io/v1'

    def _headers(self):
        return {'xi-api-key': self._api_key()}

    def submit(self, client, payload):
        voice = payload.get('voice_id', 'default')
        resp = client.post(
            f'{self.base_url}/text-to-speech/{voice}',
            json={'text': payload.get('text', '')}, headers=self._headers())
        resp.raise_for_status()
        # TTS renvoie directement les octets audio : on porte le contenu.
        return resp.content

    def poll(self, client, job_id):
        # ``submit`` a déjà renvoyé les octets audio (synchrone) — on les rend.
        return job_id


class Json2videoAdapter(CreativeFactoryAdapter):
    """Assemblage d'explainers (JSON2Video)."""

    env_key = 'JSON2VIDEO_API_KEY'
    source_lane = 'json2video'
    default_asset_type = CreativeAsset.AssetType.EXPLAINER
    default_ext = 'mp4'
    default_content_type = 'video/mp4'
    base_url = 'https://api.json2video.com/v2'

    def _headers(self):
        return {'x-api-key': self._api_key()}

    def submit(self, client, payload):
        resp = client.post(
            f'{self.base_url}/movies', json=payload.get('input', {}),
            headers=self._headers())
        resp.raise_for_status()
        return resp.json().get('project')

    def poll(self, client, job_id):
        resp = client.get(
            f'{self.base_url}/movies?project={job_id}', headers=self._headers())
        resp.raise_for_status()
        movie = resp.json().get('movie') or {}
        url = movie.get('url')
        return client.get(url).content if url else None


# Registre nom → classe d'adaptateur.
ADAPTERS = {
    'zapcap': ZapcapAdapter,
    'fal': FalAdapter,
    'templated': TemplatedAdapter,
    'elevenlabs': ElevenlabsAdapter,
    'json2video': Json2videoAdapter,
}


def get_adapter(name):
    """Instancie un adaptateur par nom (ou ``None`` si inconnu)."""
    cls = ADAPTERS.get(name)
    return cls() if cls else None


def enabled_adapters():
    """Liste des noms d'adaptateurs dont la clé est présente (les autres
    no-opent). Utile pour l'endpoint santé du câblage (ENG12)."""
    return [name for name, cls in ADAPTERS.items() if cls().is_enabled()]
