# NTHOT9 — Housekeeping (statuts chambre + tâches femmes de chambre mobiles).
# Hand-authored (see 0001_initial.py note on the host Django version mismatch).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitality", "0006_parametrestaxesejour"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TacheMenage",
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
                    "type_tache",
                    models.CharField(
                        choices=[
                            ("depart", "Départ"),
                            ("recouche", "Recouche"),
                            ("nettoyage_complet", "Nettoyage complet"),
                        ],
                        default="nettoyage_complet",
                        max_length=20,
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_faire", "À faire"),
                            ("en_cours", "En cours"),
                            ("terminee", "Terminée"),
                        ],
                        default="a_faire",
                        max_length=10,
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_completion", models.DateTimeField(blank=True, null=True)),
                (
                    "assignee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hospitality_taches_menage",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "chambre",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="taches_menage",
                        to="hospitality.chambre",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_taches_menage",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tâche de ménage",
                "verbose_name_plural": "Tâches de ménage",
                "ordering": ["-date_creation"],
            },
        ),
    ]
