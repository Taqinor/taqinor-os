"""Organigramme (fondateur, 27/10/2026) — département de rattachement d'une
équipe terrain. ADDITIF : une colonne nullable.
Réversible : ``migrate installations 0133``."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0133_series_caracteristiques_photo_meta'),
        ('roles', '0012_organigramme'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipe',
            name='departement',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='equipes_terrain', to='roles.departement'),
        ),
    ]
