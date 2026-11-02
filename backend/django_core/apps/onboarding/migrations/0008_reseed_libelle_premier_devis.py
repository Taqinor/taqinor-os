"""APAR86 — porte sur les bases existantes le libellé d'APAR52.

f6265e8617 a renommé ``premier_devis`` « Créer votre 1er devis » → « Envoyer
votre 1er devis » dans ``DEFAULT_ITEMS``, mais ``seed_default_items`` n'est
appelé que par les migrations 0002/0003/0006 (déjà appliquées) : les bases
existantes gardaient l'ancien libellé. On rejoue l'upsert (par ``key``) ;
les autres clés restent identiques, aucune progression n'est touchée.
"""
from django.db import migrations


def reseed(apps, schema_editor):
    from apps.onboarding.services import seed_default_items
    OnboardingChecklistItem = apps.get_model(
        'onboarding', 'OnboardingChecklistItem')
    seed_default_items(model=OnboardingChecklistItem)


def noop_reverse(apps, schema_editor):
    # Données de catalogue additives — jamais défaites au reverse (cf. 0006).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0007_ntdmo28_masque_pour'),
    ]

    operations = [
        migrations.RunPython(reseed, noop_reverse),
    ]
