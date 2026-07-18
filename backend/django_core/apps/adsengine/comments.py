"""ADSDEEP53 — Boîte de réception des commentaires (posts organiques + dark posts).

Ce module porte la logique PURE / de synchronisation des commentaires (dossier
``docs/engine/research/adsdeep-organic-posts-ig.md`` §3). Les WRITES (masquer /
répondre / supprimer / réponse privée) NE vivent PAS ici : ils passent tous par
le cycle ``EngineAction`` propose→approuve→applique de ``services.py`` — dont le
masquage avec **read-back obligatoire** (``is_hidden`` est éventuellement
consistant côté Meta : on ne le croit jamais en aveugle, on re-GET pour confirmer
avant d'allumer le badge « caché-vérifié »).

Contenu :
  * ``sync_comments`` — upsert idempotent des miroirs (préserve les drapeaux
    locaux ``hidden_verified`` / ``private_reply_sent_at`` / ``answered``) ;
  * ``matched_keyword`` / ``plan_keyword_hides`` — le moteur de règles mot-clé,
    en mode **dry-run par défaut** (aucune écriture) : il ne fait que LISTER les
    masquages qui SERAIENT proposés. Le passage à la proposition réelle vit dans
    ``services.propose_keyword_hides`` (mode PROPOSE ; auto uniquement si la règle
    porte ``auto=True``, opt-in explicite).
"""
from __future__ import annotations


def _parse_dt(value):
    """Parse un horodatage Meta (ISO 8601) en ``datetime`` aware, ou ``None``."""
    if not value:
        return None
    from django.utils.dateparse import parse_datetime
    try:
        return parse_datetime(str(value))
    except (ValueError, TypeError):
        return None


def sync_comments(company, comments, *, object_meta_id, source='post',
                  parent_meta_id=''):
    """ADSDEEP53 — Upsert idempotent des miroirs de commentaires d'UN objet.

    ``object_meta_id`` = le post organique (``PagePostMirror.meta_id``) OU
    l'``effective_object_story_id`` d'un dark post ; ``source`` ∈ {post, ad}.
    Idempotent par ``(company, meta_id)`` : une re-synchro écrase les champs
    LECTURE (message/auteur/compteurs/is_hidden) mais NE TOUCHE JAMAIS aux
    drapeaux d'état LOCAUX (``hidden_verified``, ``private_reply_sent_at``,
    ``answered``) — ceux-ci sont posés par le cycle d'actions, pas par la synchro.
    Renvoie la liste des miroirs."""
    from django.utils import timezone

    from .models import CommentMirror

    mirrors = []
    for c in comments or []:
        mid = str(c.get('id') or '').strip()
        if not mid:
            continue
        frm = c.get('from') or {}
        parent = c.get('parent') or {}
        parent_id = (str((parent or {}).get('id') or '').strip()
                     or str(parent_meta_id or '').strip())
        fields = {
            'object_meta_id': str(object_meta_id or ''),
            'source': source,
            'parent_meta_id': parent_id,
            'message': c.get('message', '') or '',
            'from_name': str((frm or {}).get('name') or ''),
            'from_id': str((frm or {}).get('id') or ''),
            'created_time': _parse_dt(c.get('created_time')),
            'like_count': int(c.get('like_count') or 0),
            'reply_count': int(c.get('comment_count') or 0),
            'is_hidden': bool(c.get('is_hidden', False)),
            'can_hide': bool(c.get('can_hide', True)),
            'can_remove': bool(c.get('can_remove', True)),
            'permalink': c.get('permalink_url', '') or '',
            'fetched_at': timezone.now(),
        }
        obj, _ = CommentMirror.objects.update_or_create(
            company=company, meta_id=mid, defaults=fields)
        mirrors.append(obj)
    return mirrors


def matched_keyword(message, rules):
    """ADSDEEP53 — Renvoie le PREMIER mot-clé (règle activée) contenu dans
    ``message`` (comparaison « contient », insensible à la casse), ou ``None``.
    Fonction PURE — aucune E/S, aucun effet de bord."""
    text = str(message or '').lower()
    if not text:
        return None
    for rule in rules or []:
        kw = str(getattr(rule, 'keyword', '') or '').strip().lower()
        if kw and kw in text:
            return rule
    return None


def plan_keyword_hides(company, *, rules=None):
    """ADSDEEP53 — DRY-RUN du moteur de règles mot-clé : liste les commentaires
    VISIBLES (non déjà masqués) qui MATCHENT une règle activée, SANS rien écrire
    (aucune ``EngineAction`` créée). Renvoie une liste de dicts
    ``{comment_id, comment, keyword, auto}`` — la prévisualisation exacte de ce
    que ``services.propose_keyword_hides`` proposerait. C'est le mode par défaut :
    un opérateur inspecte le plan avant de proposer/activer quoi que ce soit."""
    from .models import CommentKeywordRule, CommentMirror

    if rules is None:
        rules = list(
            CommentKeywordRule.objects.filter(company=company, enabled=True))
    if not rules:
        return []
    plan = []
    visibles = CommentMirror.objects.filter(company=company, is_hidden=False)
    for comment in visibles:
        rule = matched_keyword(comment.message, rules)
        if rule is None:
            continue
        plan.append({
            'comment_id': comment.pk,
            'comment': comment,
            'keyword': rule.keyword,
            'auto': bool(rule.auto),
        })
    return plan
