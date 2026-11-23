"""ACAL1333 — le dernier verdict « Prêt à envoyer ? » rangé sur le calepinage.

Additive et réversible : une colonne JSON neuve, ``NULL`` (jamais lu) pour tout
l'existant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0042_etat_conception'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='dernier_verdict',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name='Dernier verdict « Prêt à envoyer ? »'),
        ),
    ]
