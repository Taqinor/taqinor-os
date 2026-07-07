"""Deterministic time helper for tests (YTEST15).

Any test whose assertions depend on ``timezone.now()`` (a deadline check, a
"created in the last 24h" query, a relance/follow-up schedule…) is flaky by
construction unless the clock is frozen. Wrap the dep-light ``freezegun``
(requirements-dev.txt) so callers don't need to remember the import path or
the France/UTC-aware gotcha (Django's ``timezone.now()`` is tz-aware; freeze
with a tz-aware datetime to match).

    from testkit.time import frozen

    def test_devis_expires_after_30_days(self):
        with frozen('2026-01-01 10:00:00'):
            devis = DevisFactory(date_validite=date(2026, 1, 31))
        with frozen('2026-02-01 00:00:01'):
            self.assertTrue(devis.est_expire())

Faker: seed it explicitly wherever random-but-realistic data matters
(``Faker.seed(1234)`` at module import, or per-test via
``faker.Faker().seed_instance(1234)``) — never rely on Faker's own random
seed, which changes every run.
"""
from freezegun import freeze_time


def frozen(when):
    """Freeze time at ``when`` (any value ``freezegun`` accepts: an ISO
    string, a ``datetime``, a ``date``). Returns a context manager / decorator
    (same API as ``freeze_time`` — use as ``with frozen(...):`` or
    ``@frozen(...)`` on a test method)."""
    return freeze_time(when)
