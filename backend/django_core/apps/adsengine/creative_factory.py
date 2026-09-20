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


# ══════════════════════════════════════════════════════════════════════════
# PUB126 — Étiquette « généré par IA » PAR LANE de fabrique.
# Meta exige la divulgation du contenu généré par IA. La lane de production est
# la source de vérité la plus fiable : la génération de copie (``gen``), la
# recombinaison (``recombine``) et les visuels génératifs (``fal``) produisent
# du contenu IA ; une photo de chantier ou un UGC réel n'en produit PAS et ne
# doit JAMAIS être sur-étiqueté (une fausse divulgation est aussi un mensonge).
# Toute lane ABSENTE de cet ensemble est traitée comme NON-IA : on n'étiquette
# jamais par défaut — une lane qui produit de l'IA s'y déclare explicitement
# (c'est ce que feront les lanes gated ``fal``/template-vidéo à leur arrivée).
#
# L'ÉTIQUETTE S'HÉRITE DU PARENT. Les lanes de recombinaison du repo
# (``zapcap``/``templated``, pilotées par ``recombine.py``) sont
# SUBSTITUTION-ONLY — ``_assert_substitution_only`` interdit tout champ
# génératif : coller une accroche RÉELLE sur une photo de chantier RÉELLE ne
# fabrique aucun contenu IA, et l'étiqueter le serait une divulgation FAUSSE
# (Reda : jamais de sur-étiquetage d'un asset chantier réel). En revanche, une
# variante DÉRIVÉE d'un asset IA reste de l'IA : ``asset_is_ai_generated``
# hérite donc du ``parent``. La divulgation suit le CONTENU, pas la plomberie.
# ══════════════════════════════════════════════════════════════════════════
AI_GENERATED_LANES = frozenset({'gen', 'recombine', 'fal'})


def lane_is_ai_generated(source_lane):
    """PUB126 — Vrai si la lane de fabrique ``source_lane`` produit du contenu
    généré par IA (donc à divulguer). Lane inconnue / vide ⇒ ``False``."""
    return str(source_lane or '') in AI_GENERATED_LANES


def asset_is_ai_generated(source_lane, parent=None):
    """PUB126 — Étiquette IA d'un asset en PRODUCTION : sa lane génère de l'IA,
    OU il dérive d'un parent déjà étiqueté (une variante d'un asset IA reste de
    l'IA). Jamais vrai pour une substitution d'assets réels."""
    return (lane_is_ai_generated(source_lane)
            or bool(getattr(parent, 'ai_generated', False)))


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
            # PUB126 — divulgation IA posée PAR LA LANE, héritée du parent
            # (jamais par l'appelant : le payload ne peut pas la contredire).
            ai_generated=asset_is_ai_generated(self.source_lane, parent),
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


# ══════════════════════════════════════════════════════════════════════════
# PUB122 — Upload d'un asset de la créathèque VERS LE COMPTE publicitaire.
# ``CreativeAsset.file_key`` est une clé MinIO : Meta ne sait pas la lire. Tant
# qu'un asset n'a pas d'``image_hash``/``video_id`` de COMPTE, aucun créatif
# publicitaire ne peut le référencer. Ce service fait le pont, une seule fois
# par asset (IDEMPOTENT), et n'écrit JAMAIS de statut : un média uploadé ne
# diffuse rien (invariant permanent règle #3).
# ══════════════════════════════════════════════════════════════════════════
VIDEO_ASSET_TYPES = (
    CreativeAsset.AssetType.REEL, CreativeAsset.AssetType.EXPLAINER)


def upload_asset_to_account(company, asset, *, client, media_url='',
                            image_bytes=None):
    """PUB122 — Upload le média d'``asset`` au compte publicitaire et PERSISTE
    l'identifiant rendu (``meta_image_hash`` ou ``meta_video_id``).

    Routage par type : un statique part sur ``adimages`` (octets ou URL), un
    reel / explainer sur ``advideos`` (``file_url`` — une URL présignée MinIO
    suffit, Meta va chercher le fichier).

    IDEMPOTENT : un asset qui porte déjà son identifiant est renvoyé tel quel,
    SANS le moindre appel réseau (``skipped``). Une erreur Graph laisse l'asset
    INTACT (aucune écriture) et remonte une raison FR — jamais un identifiant
    partiel en base.

    Renvoie ``{'uploaded', 'skipped', 'image_hash', 'video_id', 'error',
    'message'}``."""
    from .meta_client import MetaClient, MetaError

    def _result(**kwargs):
        base = {'uploaded': False, 'skipped': False, 'image_hash': '',
                'video_id': '', 'error': None, 'message': ''}
        base.update(kwargs)
        return base

    if asset.company_id != getattr(company, 'id', company):
        return _result(
            error='autre_societe',
            message="Cet asset appartient à une autre société — upload refusé.")

    is_video = asset.asset_type in VIDEO_ASSET_TYPES
    existing = asset.meta_video_id if is_video else asset.meta_image_hash
    if existing:
        return _result(
            skipped=True,
            image_hash='' if is_video else existing,
            video_id=existing if is_video else '',
            message="Média déjà présent sur le compte — aucun ré-upload.")

    try:
        if is_video:
            payload = client.upload_ad_video(file_url=media_url)
            new_id = str((payload or {}).get('id') or '')
            if not new_id:
                return _result(
                    error='sans_identifiant',
                    message=("Upload vidéo : Meta n'a renvoyé aucun "
                             "identifiant — asset inchangé."))
            asset.meta_video_id = new_id
            asset.save(update_fields=['meta_video_id', 'updated_at'])
            return _result(
                uploaded=True, video_id=new_id,
                message='Vidéo uploadée sur le compte publicitaire.')

        payload = client.upload_ad_image(
            image_bytes=image_bytes, image_url=media_url,
            name=asset.file_key or '')
        new_hash = MetaClient.image_hash_from_payload(payload)
        if not new_hash:
            return _result(
                error='sans_hash',
                message=("Upload image : Meta n'a renvoyé aucun hash — asset "
                         "inchangé."))
        asset.meta_image_hash = new_hash
        asset.save(update_fields=['meta_image_hash', 'updated_at'])
        return _result(
            uploaded=True, image_hash=new_hash,
            message='Image uploadée sur le compte publicitaire.')
    except MetaError as exc:
        logger.warning(
            'upload_asset_to_account: asset %s — erreur Meta: %s',
            asset.pk, exc)
        return _result(
            error='erreur_meta',
            message=f"Upload refusé par Meta : {exc}")


def _active_photo_consent(company, client_id, *, now=None):
    """PUB73 — Consentement PHOTO actif d'un client (ou None). Réutilise la
    garde PUB75 (couvre au moins la portée ``photo``)."""
    from .models import ConsentRecord

    if not client_id:
        return None
    for consent in ConsentRecord.objects.filter(
            company=company, client_id=client_id, revoked_at__isnull=True):
        if consent.is_active(now=now) and consent.covers('photo'):
            return consent
    return None


def import_chantier_photo(company, *, chantier_id, attachment_id, client_id,
                          puissance_kwc=None, ville=None, note='',
                          auto_flagged=False, now=None):
    """PUB73 — Importe une photo de CHANTIER (``records.Attachment``) dans la
    créathèque comme ``CreativeAsset(source_lane='chantier')``.

    Les techniciens uploadent déjà des photos géotaguées ; les meilleures
    n'atteignaient jamais la bibliothèque créative. Cette action (sélection
    manuelle, ou import auto FLAGGÉ via ``auto_flagged``) crée un asset PENDING
    avec la provenance chantier + les métadonnées ville/kWc. **BLOQUÉ sans
    consentement client actif (PUB75, portée photo)** — refus EXPLIQUÉ, jamais un
    usage d'image sans accord. Lecture cross-app de la photo via
    ``installations.selectors`` (jamais un import de ses modèles).

    Renvoie ``{imported, blocked_reason, asset}`` — ``blocked_reason`` (FR, ou
    None) : ``consentement_manquant`` ou ``photo_introuvable``."""
    from apps.installations import selectors as inst_selectors

    from .models import CreativeAsset

    consent = _active_photo_consent(company, client_id, now=now)
    if consent is None:
        return {'imported': False, 'asset': None,
                'blocked_reason': 'consentement_manquant',
                'message': ("Consentement photo client manquant (CNDP) : "
                            "importez seulement une photo dont le client a "
                            "signé l'usage de son image.")}

    attachment = inst_selectors.chantier_photo(
        company, chantier_id, attachment_id)
    if attachment is None:
        return {'imported': False, 'asset': None,
                'blocked_reason': 'photo_introuvable',
                'message': "Photo de chantier introuvable pour ce chantier."}

    resolved_ville = ville or inst_selectors.chantier_ville(company, chantier_id)
    # Métadonnées ville/kWc portées en clair sur l'accroche (provenance lisible)
    # — la provenance MACHINE reste ``source_lane='chantier'``.
    meta_bits = []
    if puissance_kwc:
        meta_bits.append(f'{puissance_kwc:g} kWc')
    if resolved_ville:
        meta_bits.append(f'à {resolved_ville}')
    hook = 'Chantier' + (' — ' + ' '.join(meta_bits) if meta_bits else '')

    asset = CreativeAsset.objects.create(
        company=company,
        asset_type=CreativeAsset.AssetType.STATIC,
        file_key=getattr(attachment, 'file_key', '') or '',
        source_lane='chantier',
        depicts_real_client=True,
        consent=consent,
        consent_scopes_required=['photo'],
        hook_text=hook,
        primary_text=note or '',
        policy_stamp={},  # PENDING — check-list humaine (ENG16) requise
        # PUB126 — photo de chantier RÉELLE : aucune divulgation IA (jamais de
        # sur-étiquetage — la lane ``chantier`` ne génère rien).
        ai_generated=lane_is_ai_generated('chantier'),
    )
    return {'imported': True, 'asset': asset, 'blocked_reason': None,
            'auto_flagged': bool(auto_flagged),
            'message': 'Photo importée dans la créathèque (en attente de validation).'}


def brand_kit_payload(company):
    """PUB83 — Kit de marque PERSISTANT d'une société pour le ``TemplatedAdapter``
    (ou ``{}`` si aucun kit défini). Lecture seule ; jamais un secret."""
    from .models import BrandKit

    kit = BrandKit.objects.filter(company=company).first()
    return kit.as_payload() if kit is not None else {}


class TemplatedAdapter(CreativeFactoryAdapter):
    """Stamps de marque (Templated.io)."""

    env_key = 'TEMPLATED_API_KEY'
    source_lane = 'templated'
    default_asset_type = CreativeAsset.AssetType.STATIC
    default_ext = 'png'
    default_content_type = 'image/png'
    base_url = 'https://api.templated.io/v1'

    def run(self, company, payload=None, *, http_client=None, parent=None):
        """PUB83 — Injecte le kit de marque PERSISTANT (``BrandKit``) dans le
        payload de rendu AVANT l'appel Templated — au lieu d'un payload de marque
        ad hoc. Le kit prime sur un ``brand_kit`` fourni dans le payload (source
        de vérité unique). Sans kit défini : comportement inchangé."""
        payload = dict(payload or {})
        kit = brand_kit_payload(company)
        if kit:
            merged_input = dict(payload.get('input') or {})
            merged_input['brand_kit'] = kit
            payload['input'] = merged_input
        return super().run(
            company, payload, http_client=http_client, parent=parent)

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


# Adaptateurs produisant des STATIQUES (pour les variantes ENG18), par priorité.
STATIC_ADAPTERS = ('fal', 'templated')


def _first_enabled_static_adapter():
    """Premier adaptateur statique activé (fal puis templated), ou ``None``."""
    for name in STATIC_ADAPTERS:
        adapter = ADAPTERS[name]()
        if adapter.is_enabled():
            return adapter
    return None


def generate_variants(base_asset, *, brand_fields=None, count=2,
                      http_client=None):
    """ENG18 — Génère 2-3 variantes STATIQUES d'un asset de base APPROUVÉ.

    À partir d'un asset de base dont la policy est VALIDÉE (``is_policy_passed``)
    et des champs de marque, produit ``count`` (borné 1-3) variantes via le
    premier adaptateur statique activé (fal / Templated, gated). Chaque variante
    est créée en stamp policy PENDING (elle doit repasser la check-list humaine)
    et LIÉE à l'asset parent (``parent=base_asset``).

    NO-OP (renvoie ``[]``) si l'asset de base n'est pas validé, ou si aucun
    adaptateur statique n'a de clé. Renvoie la liste des variantes créées.
    """
    if not base_asset.is_policy_passed:
        logger.info(
            'generate_variants: asset %s non validé policy — no-op',
            base_asset.pk)
        return []
    adapter = _first_enabled_static_adapter()
    if adapter is None:
        logger.info('generate_variants: aucun adaptateur statique activé — no-op')
        return []
    count = max(1, min(3, int(count or 2)))
    variants = []
    for index in range(count):
        payload = {
            'asset_type': CreativeAsset.AssetType.STATIC,
            'input': {**(brand_fields or {}), 'variant_index': index},
        }
        asset = adapter.run(
            base_asset.company, payload,
            http_client=http_client, parent=base_asset)
        if asset is not None:
            variants.append(asset)
    return variants
