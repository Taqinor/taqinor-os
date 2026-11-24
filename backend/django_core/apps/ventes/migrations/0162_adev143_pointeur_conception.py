"""ADEV143 (D-ACAL-97) — ``Devis.conception_source`` : la version de conception
du lead dont le devis est né (``{id, version, empreinte}``). Ajout nullable,
réversible ; aucune donnée existante touchée (les devis d'avant restent sans
pointeur et se rafraîchissent comme avant)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0161_conceptionlead'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='conception_source',
            field=models.JSONField(blank=True, default=None, editable=False, null=True),
        ),
    ]
