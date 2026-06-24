"""Migration additive : ajout du champ ``confidentialite`` sur ``Contrat``.

Valeur par défaut : ``interne`` (protège les données existantes sans sur-exposer
les contrats déjà créés). Migration réversible (``RemoveField``).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0004_contrat_sav_contrat_maintenance_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrat",
            name="confidentialite",
            field=models.CharField(
                choices=[
                    ("public", "Public"),
                    ("interne", "Interne"),
                    ("confidentiel", "Confidentiel"),
                ],
                default="interne",
                max_length=20,
                verbose_name="Confidentialité",
            ),
        ),
    ]
