# NTHOT5 — Check-in avec fiche de police marocaine imprimable.
# Hand-authored (see 0001_initial.py note on the host Django version mismatch).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitality", "0003_reservation"),
    ]

    operations = [
        migrations.CreateModel(
            name="FicheClient",
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
                ("nom_complet", models.CharField(max_length=200)),
                ("nationalite", models.CharField(max_length=100)),
                (
                    "type_piece",
                    models.CharField(
                        choices=[("cin", "CIN"), ("passeport", "Passeport")],
                        max_length=10,
                    ),
                ),
                ("numero_piece", models.CharField(max_length=50)),
                ("date_naissance", models.DateField()),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_fiches_client",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "reservation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fiches_client",
                        to="hospitality.reservation",
                        verbose_name="Réservation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Fiche de police",
                "verbose_name_plural": "Fiches de police",
                "ordering": ["id"],
            },
        ),
    ]
