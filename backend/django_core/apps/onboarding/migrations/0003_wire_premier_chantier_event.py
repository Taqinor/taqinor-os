"""WIR59 — câble `premier_chantier` sur un événement réel (`event_key`
passe de '' à 'chantier', voir `apps/onboarding/receivers.py`).

Re-exécute `seed_default_items` (idempotent, upsert par `key`) exactement
comme la migration 0002 — même patron (data migration plutôt qu'un
get_or_create au runtime, pour que le catalogue seedé reflète TOUJOURS le
`DEFAULT_ITEMS` courant de `services.py`, dans un environnement neuf comme
existant)."""
from django.db import migrations


def seed_items(apps, schema_editor):
    from apps.onboarding.services import seed_default_items
    OnboardingChecklistItem = apps.get_model('onboarding', 'OnboardingChecklistItem')
    seed_default_items(model=OnboardingChecklistItem)


def noop_reverse(apps, schema_editor):
    # Additive-only seed data — jamais supprimée au reverse (même patron que 0002).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0002_seed_default_items'),
    ]

    operations = [
        migrations.RunPython(seed_items, noop_reverse),
    ]
