"""XPLT19 — Backfill NON destructif : chaque compte existant devient membre de
sa propre société (``societes_autorisees`` = {``company``}).

Défaut = la société actuelle → ZÉRO changement de comportement pour l'existant :
un compte mono-société ne peut opérer que sa société (il ne peut pas switcher).
Idempotent (``get_or_create`` sur la table de liaison) ; le sens inverse est un
no-op volontaire (retirer l'appartenance à sa propre société n'aurait aucun
sens et la résolution de société active union-ne de toute façon la société
d'attache).
"""
from django.db import migrations


def backfill(apps, schema_editor):
    CustomUser = apps.get_model('authentication', 'CustomUser')
    Through = CustomUser.societes_autorisees.through
    for user_id, company_id in (
            CustomUser.objects
            .filter(company__isnull=False)
            .values_list('id', 'company_id')):
        Through.objects.get_or_create(
            customuser_id=user_id, company_id=company_id)


def noop(apps, schema_editor):
    # Réversible sans effet : le backfill est idempotent et additive-only.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0015_customuser_societes_autorisees'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
