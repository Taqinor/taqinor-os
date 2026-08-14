"""NTDMO14 — seed le catalogue global des 6 visites guidées (product tours).

Data migration (même patron que 0002_seed_default_items.py) : le catalogue
existe toujours, y compris sur une base de test fraîchement construite, avant
tout appel au sélecteur ``tours_pour_utilisateur``. Idempotent par
``(tour_key, ordre)``.
"""
from django.db import migrations


def seed_steps(apps, schema_editor):
    from apps.onboarding.services import seed_default_tour_steps
    ProductTourStep = apps.get_model('onboarding', 'ProductTourStep')
    seed_default_tour_steps(model=ProductTourStep)


def noop_reverse(apps, schema_editor):
    # Additive-only seed data — jamais supprimée au reverse (même patron que
    # 0002_seed_default_items.py).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0004_producttourstep_tourprogress'),
    ]

    operations = [
        migrations.RunPython(seed_steps, noop_reverse),
    ]
