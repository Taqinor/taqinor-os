"""
Collision-proof document reference numbering (DEV-/BC-/FAC-YYYYMM-NNNN).

The old logic counted existing rows and used count+1, which collides as soon
as a document is deleted or numbers don't match the count (the count shrinks
but the highest used number stays). Instead we:

  1. take the highest trailing number actually used for this company and
     month prefix and add 1 — gaps and pre-existing rows are always cleared;
  2. retry a few times on a duplicate-reference IntegrityError so two
     concurrent saves can never crash — the loser of the race simply picks
     the next number.

References stay per-company (tenant-scoped); the DB unique constraint
(company, reference) is the final arbiter.
"""
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

_SUFFIX_RE = re.compile(r'-(\d+)$')
MAX_ATTEMPTS = 5


def _period_segment(period):
    """Date segment for the reset period. Defaults to monthly (historical)."""
    if period == 'yearly':
        return timezone.now().strftime('%Y')
    if period == 'none':
        return ''
    # 'monthly' (et toute valeur inconnue) = comportement historique YYYYMM.
    return timezone.now().strftime('%Y%m')


def _bucket_prefix(doc_prefix, period):
    """Radical de recherche/affichage : 'DEV-202606', 'DEV-2026' ou 'DEV'."""
    seg = _period_segment(period)
    return f"{doc_prefix}-{seg}" if seg else str(doc_prefix)


def next_reference(model, doc_prefix, company, *, padding=4, period='monthly'):
    """Next free reference for this company/period.

    Defaults (padding 4, monthly reset) reproduce EXACTLY the historical
    'DEV-202606-0003'. `period` ∈ {'monthly','yearly','none'} drives the reset
    bucket; `padding` the zero-pad width. The highest-used+1 rule (gap-free,
    race-safe) is unchanged — only the bucket radical and pad width vary.
    """
    prefix = _bucket_prefix(doc_prefix, period)
    refs = model.objects.filter(
        company=company, reference__startswith=prefix,
    ).values_list('reference', flat=True)
    highest = 0
    for ref in refs:
        m = _SUFFIX_RE.search(ref)
        if m:
            highest = max(highest, int(m.group(1)))
    try:
        width = max(1, int(padding))
    except (TypeError, ValueError):
        width = 4
    return f"{prefix}-{highest + 1:0{width}d}"


def create_with_reference(model, doc_prefix, company, save_fn, *,
                          padding=4, period='monthly'):
    """Run save_fn(reference) inside a savepoint, retrying on reference races.

    save_fn receives the generated reference and must perform the actual
    create (serializer.save(...) or Model.objects.create(...)) and return
    the instance. Non-reference IntegrityErrors are re-raised immediately.
    `padding`/`period` are forwarded to next_reference (defaults = historical).
    """
    last_exc = None
    for _ in range(MAX_ATTEMPTS):
        reference = next_reference(
            model, doc_prefix, company, padding=padding, period=period)
        try:
            with transaction.atomic():
                return save_fn(reference)
        except IntegrityError as exc:
            if 'reference' not in str(exc).lower():
                raise
            last_exc = exc
    raise last_exc
