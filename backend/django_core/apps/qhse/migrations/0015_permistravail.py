# Generated for QHSE23 — Permis de travail (hauteur / consignation / point chaud)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0014_evaluationrisque_ligneevaluationrisque"),
    ]

    operations = [
        migrations.CreateModel(
            name="PermisTravail",
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
                    "reference",
                    models.CharField(
                        blank=True, default="", max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "titre",
                    models.CharField(max_length=255, verbose_name="Titre"),
                ),
                (
                    "type_permis",
                    models.CharField(
                        choices=[
                            ("hauteur", "Travail en hauteur"),
                            ("consignation_elec", "Consignation électrique"),
                            ("point_chaud", "Point chaud (soudure / flamme)"),
                            ("espace_confine", "Espace confiné"),
                            ("autre", "Autre"),
                        ],
                        default="hauteur",
                        max_length=20,
                        verbose_name="Type de permis",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("valide", "Validé"),
                            ("cloture", "Clôturé"),
                            ("expire", "Expiré"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du chantier",
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Début de validité",
                    ),
                ),
                (
                    "date_fin",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Fin de validité",
                    ),
                ),
                (
                    "delivre_par",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Délivré par",
                    ),
                ),
                (
                    "valide_par",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Validé par",
                    ),
                ),
                (
                    "mesures_prevention",
                    models.TextField(
                        blank=True, default="",
                        verbose_name="Mesures de prévention",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True, default="", verbose_name="Notes"
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
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_permis_travail",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Permis de travail",
                "verbose_name_plural": "Permis de travail",
                "ordering": ["-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="permistravail",
            constraint=models.UniqueConstraint(
                fields=["company", "reference"],
                name="qhse_permis_co_ref_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="permistravail",
            index=models.Index(
                fields=["company", "statut"],
                name="qhse_permis_co_statut",
            ),
        ),
        migrations.AddIndex(
            model_name="permistravail",
            index=models.Index(
                fields=["company", "type_permis"],
                name="qhse_permis_co_type",
            ),
        ),
        migrations.AddIndex(
            model_name="permistravail",
            index=models.Index(
                fields=["company", "chantier_id"],
                name="qhse_permis_co_chant",
            ),
        ),
    ]
