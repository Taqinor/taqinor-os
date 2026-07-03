# Generated for XFLT9 — plafond CGI d'amortissement des véhicules de tourisme.
# Ajoute le modèle ``ParametreAmortissementCGI`` : plafond TTC éditable par
# société (défaut 400 000 DH TTC, LF 2025). Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0034_pleincarburant_tva"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametreAmortissementCGI",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "plafond_ttc",
                    models.DecimalField(
                        decimal_places=2, default=400000, max_digits=12,
                        verbose_name="Plafond CGI (DH TTC)",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_parametre_amortissement_cgi",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Paramètre d'amortissement CGI",
                "verbose_name_plural": "Paramètres d'amortissement CGI",
            },
        ),
    ]
