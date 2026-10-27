"""Organigramme (fondateur, 27/10/2026) — département de rattachement d'une
équipe commerciale. ADDITIF : une colonne nullable.
Réversible : ``migrate crm 0141``."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0142_categories_commerce_talon'),
        ('roles', '0012_organigramme'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipecommerciale',
            name='departement',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='equipes_commerciales', to='roles.departement'),
        ),
    ]
