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


def detect_reference_gaps(model, doc_prefix, company):
    """Detect gaps in the per-(company, doc_prefix, period) sequence (N11).

    Builds on the SAME prefix scheme as next_reference (does NOT change it):
    groups existing references by their YYYYMM period and, within each period,
    reports any missing number between 1 and the highest used. WARNS only —
    a gap is normal after a deletion; this just surfaces it for the admin.

    Returns a list of dicts: {period, prefix, missing: [ints], expected_max,
    present_count}.
    """
    refs = model.objects.filter(
        company=company, reference__startswith=f"{doc_prefix}-",
    ).values_list('reference', flat=True)

    by_period = {}
    period_re = re.compile(
        rf'^{re.escape(doc_prefix)}-(\d{{6}})-(\d+)$')
    for ref in refs:
        m = period_re.match(ref)
        if not m:
            continue
        period, num = m.group(1), int(m.group(2))
        by_period.setdefault(period, set()).add(num)

    report = []
    for period in sorted(by_period):
        used = by_period[period]
        top = max(used)
        missing = [n for n in range(1, top + 1) if n not in used]
        if missing:
            report.append({
                'period': period,
                'prefix': f"{doc_prefix}-{period}",
                'missing': missing,
                'expected_max': top,
                'present_count': len(used),
            })
    return report


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
