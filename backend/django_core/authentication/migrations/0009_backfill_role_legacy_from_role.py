"""Backfill NON destructif : réaligne ``role_legacy`` sur le palier du Role
assigné, pour les comptes déjà créés.

Avant correctif, ``role_legacy`` restait figé à 'normal' à la création/mise à
jour d'un utilisateur, quel que soit son Role — un Administrateur/Responsable
héritait donc du menu limité. Cette migration corrige les comptes existants
sans aucune re-création : elle ne modifie que le champ legacy quand il diverge
du palier du rôle, ne supprime ni ne crée rien. Le sens inverse est un no-op
volontaire (on ne restaure pas les anciennes valeurs dérivées).
"""
from django.db import migrations

from authentication.role_tiers import sync_role_legacy


def backfill(apps, schema_editor):
    User = apps.get_model('authentication', 'CustomUser')
    sync_role_legacy(User)


def noop(apps, schema_editor):
    # Réversible sans effet : rien à défaire, le backfill est idempotent.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
