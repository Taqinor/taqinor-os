"""NTADM21 — garde-fou de délégation : champ `perimetre` sur `roles.Role`.

Additif pur : colonne nullable, aucun backfill. NULL = délégation GLOBALE =
comportement historique pour tous les rôles existants.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0002_ntadm3_role_entites_visibles'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='perimetre',
            field=models.CharField(
                blank=True,
                choices=[('rh', 'RH & Paie'), ('ventes', 'Ventes & CRM')],
                default=None,
                help_text='Vide = délégation globale (aucune restriction).',
                max_length=10, null=True,
                verbose_name='Périmètre de délégation'),
        ),
    ]
