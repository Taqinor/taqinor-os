"""NTDMO26 — ajoute au catalogue 2 items du wizard first-run « société réelle » :
``assistant_demarrage`` (suivi du wizard lui-même) et ``premier_produit``
(sous-étape « ajouter un produit »). Même patron que 0002_seed_default_items.py
(idempotent par ``key``, additive-only) — `seed_default_items` upserte
maintenant 8 clés au lieu de 6, les 6 existantes restent inchangées.
"""
from django.db import migrations


def seed_items(apps, schema_editor):
    from apps.onboarding.services import seed_default_items
    OnboardingChecklistItem = apps.get_model('onboarding', 'OnboardingChecklistItem')
    seed_default_items(model=OnboardingChecklistItem)


def noop_reverse(apps, schema_editor):
    # Additive-only seed data — jamais supprimée au reverse (même patron que
    # 0002_seed_default_items.py).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0005_seed_default_tour_steps'),
    ]

    operations = [
        migrations.RunPython(seed_items, noop_reverse),
    ]
