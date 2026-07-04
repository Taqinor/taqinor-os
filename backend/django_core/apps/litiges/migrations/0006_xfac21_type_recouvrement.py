# XFAC21 — Dossier contentieux / passage en recouvrement externe. Choices-only
# (aucun changement de colonne) : ajoute 'recouvrement' aux types de
# réclamation existants.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("litiges", "0005_litige5_concurrent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reclamation",
            name="type_reclamation",
            field=models.CharField(
                choices=[
                    ("financier", "Financier"),
                    ("qualite", "Qualité"),
                    ("delai", "Délai"),
                    ("commercial", "Commercial"),
                    ("recouvrement", "Recouvrement"),
                    ("autre", "Autre"),
                ],
                default="autre", max_length=20,
                verbose_name="Type de réclamation"),
        ),
    ]
