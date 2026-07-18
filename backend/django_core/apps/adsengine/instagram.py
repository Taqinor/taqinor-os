"""ADSDEEP55 — Instagram (compte Business relié à la Page).

Logique PURE / de synchronisation d'Instagram (dossier
``docs/engine/research/adsdeep-organic-posts-ig.md`` §4). Les WRITES (publier via
le flux container, masquer/répondre/supprimer un commentaire, couper les
commentaires d'un média) NE vivent PAS ici : ils passent tous par le cycle
``EngineAction`` propose→approuve→applique de ``services.py``.

Invariants portés par ce module :
  * la ``caption`` est LECTURE SEULE (immuable après publication) — la synchro la
    miroite, aucune fonction ne l'édite ;
  * la publication passe par le flux container (create → poll FINISHED → publish),
    orchestré dans ``meta_client.publish_ig_media`` ;
  * le quota ``50 publications / 24 h`` est LU (``publishing_limit``) et surfacé.
"""
from __future__ import annotations


def _parse_dt(value):
    if not value:
        return None
    from django.utils.dateparse import parse_datetime
    try:
        return parse_datetime(str(value))
    except (ValueError, TypeError):
        return None


def sync_ig_media(company, media_rows):
    """ADSDEEP55 — Upsert idempotent des miroirs de médias IG.

    La ``caption`` est miroitée en LECTURE (jamais éditée). Idempotent par
    ``(company, meta_id)``. Renvoie la liste des miroirs."""
    from django.utils import timezone

    from .models import InstagramMediaMirror

    mirrors = []
    for m in media_rows or []:
        mid = str(m.get('id') or '').strip()
        if not mid:
            continue
        fields = {
            'caption': m.get('caption', '') or '',
            'media_type': str(m.get('media_type') or ''),
            'media_url': m.get('media_url', '') or '',
            'permalink': m.get('permalink', '') or '',
            'like_count': int(m.get('like_count') or 0),
            'comments_count': int(m.get('comments_count') or 0),
            'view_count': int(m.get('view_count') or 0),
            'comment_enabled': bool(m.get('is_comment_enabled', True)),
            'timestamp': _parse_dt(m.get('timestamp')),
            'fetched_at': timezone.now(),
        }
        obj, _ = InstagramMediaMirror.objects.update_or_create(
            company=company, meta_id=mid, defaults=fields)
        mirrors.append(obj)
    return mirrors


def sync_ig_comments(company, comment_rows, *, media_meta_id):
    """ADSDEEP55 — Upsert idempotent des miroirs de commentaires IG d'un média.

    ``hidden``/``answered`` sont des drapeaux LOCAUX posés par le cycle d'actions
    (jamais écrasés par la synchro). Renvoie la liste des miroirs."""
    from django.utils import timezone

    from .models import InstagramCommentMirror

    mirrors = []
    for c in comment_rows or []:
        cid = str(c.get('id') or '').strip()
        if not cid:
            continue
        fields = {
            'media_meta_id': str(media_meta_id or ''),
            'parent_meta_id': str(c.get('parent_id') or ''),
            'message': c.get('text', '') or '',
            'from_username': str(c.get('username') or ''),
            'like_count': int(c.get('like_count') or 0),
            'timestamp': _parse_dt(c.get('timestamp')),
            'fetched_at': timezone.now(),
        }
        obj, _ = InstagramCommentMirror.objects.update_or_create(
            company=company, meta_id=cid, defaults=fields)
        mirrors.append(obj)
    return mirrors


def publishing_limit(client):
    """ADSDEEP55 — Quota de publication IG normalisé ``{used, total, remaining}``
    pour l'UI (bandeau « X/50 publications sur 24 h »). NO-OP défensif (renvoie
    ``None``) si le client n'expose pas ``get_ig_publishing_limit`` (mock ancien)
    ou si l'appel échoue (aucune donnée plutôt qu'une erreur qui casse l'écran)."""
    getter = getattr(client, 'get_ig_publishing_limit', None)
    if not callable(getter):
        return None
    try:
        limit = getter() or {}
    except Exception:  # noqa: BLE001 — le quota n'empêche jamais l'affichage
        return None
    used = limit.get('used')
    total = limit.get('total')
    remaining = None
    if isinstance(used, int) and isinstance(total, int):
        remaining = max(total - used, 0)
    return {'used': used, 'total': total, 'remaining': remaining}
