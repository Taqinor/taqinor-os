# GED18 — Workflow d'approbation / revue documentaire.
#
# Ajoute le modèle `DemandeApprobation` : qui demande la revue (`demandeur`),
# qui valide (`approbateur`), sa décision (`statut` en_attente/approuve/rejete),
# l'horodatage (`decision_le`) et un commentaire. À l'approbation, le service
# réutilise la machine à états GED17 (`change_lifecycle_status`) pour faire
# avancer le document « revue → approuvé » — aucun nouveau cycle de vie ici.
# Additive et réversible. Statuts LOCAUX à la GED, distincts de STAGES.py.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0011_document_statut"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandeApprobation",
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
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("approuve", "Approuvée"),
                            ("rejete", "Rejetée"),
                        ],
                        default="en_attente",
                        max_length=10,
                        verbose_name="statut de la demande",
                    ),
                ),
                ("commentaire", models.TextField(blank=True, default="")),
                (
                    "decision_le",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="décidée le"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_demandes_approbation",
                        to="authentication.company",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="demandes_approbation",
                        to="ged.document",
                    ),
                ),
                (
                    "demandeur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_demandes_approbation_emises",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="demandeur",
                    ),
                ),
                (
                    "approbateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_demandes_approbation_recues",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="approbateur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Demande d'approbation",
                "verbose_name_plural": "Demandes d'approbation",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="demandeapprobation",
            index=models.Index(
                fields=["company", "statut"], name="ged_demande_co_statut_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="demandeapprobation",
            index=models.Index(
                fields=["company", "document"], name="ged_demande_co_doc_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="demandeapprobation",
            index=models.Index(
                fields=["approbateur"], name="ged_demande_approb_idx"
            ),
        ),
    ]
