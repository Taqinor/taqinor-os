"""NTDMO11/12 — seed the global « Premiers pas » checklist catalogue.

Data migration (not a runtime signal-time get_or_create) so the catalogue
always exists — in every environment, including a freshly-built test DB —
before any ``core.events`` receiver (NTDMO12) or the progress selector
(NTDMO11) ever queries it by ``key``. Idempotent (``seed_default_items``
upserts by unique ``key``), so re-running this migration (or calling
``seed_default_items`` again later, e.g. from a management command) never
duplicates rows.
"""
from django.db import migrations


def seed_items(apps, schema_editor):
    from apps.onboarding.services import seed_default_items
    OnboardingChecklistItem = apps.get_model('onboarding', 'OnboardingChecklistItem')
    seed_default_items(model=OnboardingChecklistItem)


def noop_reverse(apps, schema_editor):
    # Additive-only seed data — never deleted on reverse (mirrors the
    # catalogue seeder pattern used elsewhere in this repo, e.g.
    # apps/stock's seed_catalogue).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_items, noop_reverse),
    ]
