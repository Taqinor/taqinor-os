"""ADSENG26 — Recombinaison créative déterministe (dd-creative-sci §b).

Croise l'accroche GAGNANTE (un ``CreativeAsset`` validé policy) avec d'autres
visuels candidats via les adaptateurs ENG17 :
  * **Templated** (statiques) — substitution des ``layers`` (texte/image) ;
  * **ZapCap** (variantes vidéo) — RÉUTILISATION du ``transcriptTaskId`` +
    ``templateId`` (style de sous-titres), jamais une nouvelle transcription.

C'est de la SUBSTITUTION de gabarits, **JAMAIS de la génération** : aucun
``prompt`` génératif n'est jamais émis (garde structurelle
``_assert_substitution_only``). Un run produit un ``CreativeGenerationBatch``
de **≤2 variantes** (cap), chacune en stamp policy PENDING. L'humain approuve
le LOT ENTIER en un geste (``approve_lot``) ; SEULE cette approbation humaine
tamponne les membres ``passed=True`` (policy héritée de l'accroche gagnante +
REVALIDÉE contre la policy courante) et les pousse au backlog. La politique
no-fake-footage reste donc structurellement intacte : rien n'est validé
automatiquement, rien n'est généré.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from . import creative_factory, policy
from .models import (
    CreativeAsset, CreativeBacklogItem, CreativeGenerationBatch,
)

logger = logging.getLogger(__name__)

# Lot ≤ 2 variantes par run (dd-creative-sci §b : jamais un flot plus rapide
# que la capacité de test de la rotation).
RECOMBINATION_CAP = 2

# Types d'asset vidéo → adaptateur ZapCap ; sinon → Templated (statique).
_VIDEO_TYPES = frozenset({
    CreativeAsset.AssetType.REEL, CreativeAsset.AssetType.EXPLAINER,
})

# Clés interdites dans un payload de substitution : leur présence signalerait
# de la GÉNÉRATION (et non de la substitution) — garde structurelle testée.
_GENERATIVE_KEYS = frozenset({'prompt', 'negative_prompt', 'model', 'seed'})


def _assert_substitution_only(payload):
    """Lève ``ValueError`` si un payload porte une clé génératrice.

    Garantit structurellement que la recombinaison est de la SUBSTITUTION de
    gabarits (layers / transcript réutilisé) et jamais de la génération.
    """
    inner = (payload or {}).get('input', {}) or {}
    offenders = _GENERATIVE_KEYS.intersection(inner.keys())
    if offenders:
        raise ValueError(
            "Recombinaison = substitution, jamais génération : clés "
            f"interdites {sorted(offenders)}.")


def _adapter_name_for(candidate):
    """Adaptateur selon le type du visuel : ZapCap (vidéo) / Templated."""
    if getattr(candidate, 'asset_type', None) in _VIDEO_TYPES:
        return 'zapcap'
    return 'templated'


def build_substitution_payload(source_hook, candidate, *, template_id='',
                               transcript_task_id=''):
    """Construit le payload de SUBSTITUTION pour un couple accroche×visuel.

    Templated : ``layers`` (accroche/corps/CTA en texte + visuel en image).
    ZapCap : ``transcriptTaskId`` RÉUTILISÉ + ``templateId`` (style). Aucun
    champ génératif — vérifié par ``_assert_substitution_only``.
    """
    name = _adapter_name_for(candidate)
    visual_ref = (getattr(candidate, 'visual_asset_key', '')
                  or getattr(candidate, 'file_key', ''))
    if name == 'zapcap':
        tid = (transcript_task_id
               or (getattr(source_hook, 'perf', {}) or {}).get(
                   'transcript_task_id', ''))
        payload = {
            'asset_type': CreativeAsset.AssetType.REEL,
            'ext': 'mp4',
            'input': {
                'transcriptTaskId': tid,        # RÉUTILISÉ (jamais régénéré)
                'templateId': template_id,
                'videoUrl': visual_ref,
            },
        }
    else:
        payload = {
            'asset_type': CreativeAsset.AssetType.STATIC,
            'ext': 'png',
            'input': {
                'template': template_id,
                'layers': {
                    'headline': {
                        'text': getattr(source_hook, 'hook_text', '')},
                    'body': {
                        'text': getattr(source_hook, 'primary_text', '')},
                    'cta': {'text': getattr(source_hook, 'cta', '')},
                    'image': {'image_url': visual_ref},
                },
            },
        }
    _assert_substitution_only(payload)
    return payload


def _stamp_lineage(asset, source_hook, candidate):
    """Reporte la lignée composant sur la variante produite : accroche héritée
    de l'accroche gagnante, visuel du candidat. La variante reste PENDING."""
    asset.hook_id = getattr(source_hook, 'hook_id', '') or ''
    asset.hook_text = getattr(source_hook, 'hook_text', '') or ''
    asset.primary_text = getattr(source_hook, 'primary_text', '') or ''
    asset.cta = getattr(source_hook, 'cta', '') or ''
    asset.visual_asset_key = (getattr(candidate, 'visual_asset_key', '')
                              or getattr(candidate, 'file_key', '') or '')
    asset.save(update_fields=[
        'hook_id', 'hook_text', 'primary_text', 'cta', 'visual_asset_key',
        'updated_at'])
    return asset


def recombine_hook_across_visuals(source_hook_asset, visual_candidates, *,
                                  http_client=None, cap=RECOMBINATION_CAP,
                                  template_id='', transcript_task_id=''):
    """Recombine une accroche GAGNANTE avec des visuels candidats (≤ cap).

    Exige que ``source_hook_asset`` soit validé policy (une accroche gagnante
    ne peut venir que d'un asset validé). Crée un ``CreativeGenerationBatch``
    (EN_ATTENTE), produit les variantes PENDING via les adaptateurs ENG17
    (no-op propre sans clé), reporte la lignée composant, et renvoie le lot.
    Ne tamponne AUCUNE variante : seule ``approve_lot`` (humain) le fait.
    """
    if not source_hook_asset.is_policy_passed:
        raise ValueError(
            "La recombinaison part d'une accroche GAGNANTE validée policy — "
            "l'asset source n'est pas validé.")
    company = source_hook_asset.company
    candidates = list(visual_candidates)[:max(0, int(cap))]
    batch = CreativeGenerationBatch.objects.create(
        company=company, source_hook_asset=source_hook_asset,
        status=CreativeGenerationBatch.Statut.EN_ATTENTE)

    produced_ids = []
    for candidate in candidates:
        name = _adapter_name_for(candidate)
        adapter = creative_factory.get_adapter(name)
        if adapter is None:
            continue
        payload = build_substitution_payload(
            source_hook_asset, candidate, template_id=template_id,
            transcript_task_id=transcript_task_id)
        asset = adapter.run(
            company, payload, http_client=http_client,
            parent=source_hook_asset)
        if asset is None:  # clé absente / poll vide → no-op propre
            continue
        _stamp_lineage(asset, source_hook_asset, candidate)
        produced_ids.append(asset.pk)

    batch.visual_ids = produced_ids
    batch.save(update_fields=['visual_ids', 'updated_at'])
    return batch


def _members(batch):
    """Variantes membres d'un lot (par les PKs stockés dans ``visual_ids``)."""
    ids = [i for i in (batch.visual_ids or []) if isinstance(i, int)]
    if not ids:
        return CreativeAsset.objects.none()
    return CreativeAsset.objects.filter(company=batch.company, pk__in=ids)


def approve_lot(batch, *, user, now=None):
    """Approuve le LOT ENTIER (approbation humaine par lot — jamais par
    variante). Tamponne chaque membre ``passed=True`` en HÉRITANT les règles
    confirmées de l'accroche gagnante puis en les REVALIDANT contre la policy
    courante (``policy.record_policy_check``), et pousse chaque membre au
    backlog. Idempotent-safe : ne ré-approuve pas un lot déjà décidé.
    Renvoie ``(batch, backlog_items)``.
    """
    if batch.status != CreativeGenerationBatch.Statut.EN_ATTENTE:
        raise ValueError(
            "Seul un lot EN ATTENTE peut être approuvé (décision par lot).")
    now = now or timezone.now()
    source = batch.source_hook_asset
    inherited = sorted(
        (getattr(source, 'policy_stamp', {}) or {}).get('rules_checked', []))

    backlog_items = []
    for member in _members(batch):
        # Héritage + REVALIDATION : passed ne devient vrai que si les règles
        # héritées couvrent TOUJOURS toutes les interdictions courantes.
        policy.record_policy_check(
            member, confirmed_keys=inherited, checked_by=user, now=now)
        item = CreativeBacklogItem.objects.create(
            company=batch.company, asset=member, batch=batch,
            source=CreativeBacklogItem.Source.RECOMBINAISON,
            status=CreativeBacklogItem.Statut.EN_FILE)
        backlog_items.append(item)

    batch.status = CreativeGenerationBatch.Statut.APPROUVEE
    batch.approved_by = user
    batch.approved_at = now
    batch.save(update_fields=['status', 'approved_by', 'approved_at',
                              'updated_at'])
    return batch, backlog_items


def reject_lot(batch, *, user, now=None):
    """Rejette le LOT ENTIER : les variantes restent PENDING et n'entrent
    jamais au backlog (no-fake-footage : rien de non-validé ne part)."""
    now = now or timezone.now()
    batch.status = CreativeGenerationBatch.Statut.REJETEE
    batch.approved_by = user
    batch.approved_at = now
    batch.save(update_fields=['status', 'approved_by', 'approved_at',
                              'updated_at'])
    return batch
