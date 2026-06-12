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


def next_reference(model, doc_prefix, company):
    """Next free reference like 'DEV-202606-0003' for this company/month."""
    prefix = f"{doc_prefix}-{timezone.now().strftime('%Y%m')}"
    refs = model.objects.filter(
        company=company, reference__startswith=prefix,
    ).values_list('reference', flat=True)
    highest = 0
    for ref in refs:
        m = _SUFFIX_RE.search(ref)
        if m:
            highest = max(highest, int(m.group(1)))
    return f"{prefix}-{highest + 1:04d}"


def create_with_reference(model, doc_prefix, company, save_fn):
    """Run save_fn(reference) inside a savepoint, retrying on reference races.

    save_fn receives the generated reference and must perform the actual
    create (serializer.save(...) or Model.objects.create(...)) and return
    the instance. Non-reference IntegrityErrors are re-raised immediately.
    """
    last_exc = None
    for _ in range(MAX_ATTEMPTS):
        reference = next_reference(model, doc_prefix, company)
        try:
            with transaction.atomic():
                return save_fn(reference)
        except IntegrityError as exc:
            if 'reference' not in str(exc).lower():
                raise
            last_exc = exc
    raise last_exc
