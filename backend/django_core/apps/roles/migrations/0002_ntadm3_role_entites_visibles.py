"""NTADM3 — périmètre de données par entité sur `roles.Role`.

Additif pur : M2M vide par défaut = aucune restriction (tous les rôles
existants voient toutes les entités, comportement inchangé).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entites', '0001_initial'),
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='entites_visibles',
            field=models.ManyToManyField(
                blank=True,
                help_text='Vide = toutes les entités sont visibles (défaut).',
                related_name='roles_visibles',
                to='entites.entite',
                verbose_name='Entités visibles'),
        ),
    ]
