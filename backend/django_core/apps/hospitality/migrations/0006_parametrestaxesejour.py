# NTHOT8 — Taxe de séjour paramétrable.
# Hand-authored (see 0001_initial.py note on the host Django version mismatch).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitality", "0005_folio_lignefolio"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametresTaxeSejour",
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
                    "montant_par_nuit_par_personne",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=8
                    ),
                ),
                ("exoneration_enfants", models.BooleanField(default=True)),
                ("actif", models.BooleanField(default=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_parametres_taxe_sejour",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Paramètres taxe de séjour",
                "verbose_name_plural": "Paramètres taxe de séjour",
            },
        ),
    ]
