"""ASEC5 — anti-rejeu TOTP : dernier pas consommé par compte.

Additive et revertable : une colonne nullable, aucune donnée touchée
(null = aucun code consommé, comportement d'origine au premier code).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0033_solmvp30b_customuser_sans_poste_ref'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='totp_dernier_pas',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
