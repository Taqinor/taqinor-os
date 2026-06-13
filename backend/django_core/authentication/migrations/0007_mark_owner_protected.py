"""Marque le compte propriétaire comme protégé (WS3).

La protection (is_protected) garantit, avec la garde « dernier propriétaire »,
qu'on ne peut jamais supprimer/rétrograder le dernier admin. Cette migration
de données pose le drapeau sur le propriétaire connu (demo_admin) et sur tout
superutilisateur, de façon idempotente et réversible — chemin reproductible,
appliqué en production par le déploiement (manage.py migrate).
"""
from django.db import migrations


def mark_protected(apps, schema_editor):
    CustomUser = apps.get_model('authentication', 'CustomUser')
    # Propriétaire connu + tout superutilisateur (compte plateforme).
    CustomUser.objects.filter(username='demo_admin').update(is_protected=True)
    CustomUser.objects.filter(is_superuser=True).update(is_protected=True)


def unmark_protected(apps, schema_editor):
    # Réversible : on retire le drapeau (sécurité de rollback uniquement).
    CustomUser = apps.get_model('authentication', 'CustomUser')
    CustomUser.objects.filter(username='demo_admin').update(is_protected=False)


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0006_customuser_is_protected'),
    ]

    operations = [
        migrations.RunPython(mark_protected, unmark_protected),
    ]
