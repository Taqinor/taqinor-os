# Generated for QHSE24 — Consignation électrique (LOTO) sur permis électrique

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0015_permistravail"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsignationLoto",
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
                    "equipement",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Équipement",
                    ),
                ),
                (
                    "point_consignation",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Point de consignation",
                    ),
                ),
                (
                    "consignateur",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Consignateur",
                    ),
                ),
                (
                    "date_consignation",
                    models.DateTimeField(
                        blank=True, null=True,
                        verbose_name="Date de consignation",
                    ),
                ),
                (
                    "date_deconsignation",
                    models.DateTimeField(
                        blank=True, null=True,
                        verbose_name="Date de déconsignation",
                    ),
                ),
                (
                    "cadenas_pose",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Cadenas posé",
                    ),
                ),
                (
                    "etiquette",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Étiquette",
                    ),
                ),
                (
                    "verifie_absence_tension",
                    models.BooleanField(
                        default=False,
                        verbose_name="Absence de tension vérifiée (VAT)",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("consignee", "Consignée"),
                            ("deconsignee", "Déconsignée"),
                        ],
                        default="consignee",
                        max_length=12,
                        verbose_name="Statut",
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
                        related_name="qhse_consignations_loto",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "permis",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consignations_loto",
                        to="qhse.permistravail",
                        verbose_name="Permis de travail",
                    ),
                ),
            ],
            options={
                "verbose_name": "Consignation électrique (LOTO)",
                "verbose_name_plural": "Consignations électriques (LOTO)",
                "ordering": ["-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="consignationloto",
            constraint=models.UniqueConstraint(
                fields=["company", "reference"],
                name="qhse_consigloto_co_ref_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="consignationloto",
            index=models.Index(
                fields=["company", "permis"],
                name="qhse_consigloto_co_permis",
            ),
        ),
        migrations.AddIndex(
            model_name="consignationloto",
            index=models.Index(
                fields=["company", "statut"],
                name="qhse_consigloto_co_statut",
            ),
        ),
    ]
