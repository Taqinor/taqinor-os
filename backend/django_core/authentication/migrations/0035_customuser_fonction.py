"""Organigramme (fondateur, 27/10/2026) — FONCTION du compte (``roles.Poste``).
ADDITIF : une colonne nullable, aucune donnée touchée.
Réversible : ``migrate authentication 0034``."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0034_asec5_totp_dernier_pas'),
        ('roles', '0012_organigramme'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='fonction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='titulaires', to='roles.poste'),
        ),
    ]
