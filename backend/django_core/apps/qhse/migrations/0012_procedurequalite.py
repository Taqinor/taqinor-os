# Generated for QHSE18 — Procédure qualité versionnée (docs qualité GED)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0011_notationfinchantier_itemnotation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcedureQualite",
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
                    models.CharField(max_length=80, verbose_name="Référence"),
                ),
                (
                    "titre",
                    models.CharField(max_length=255, verbose_name="Titre"),
                ),
                (
                    "version",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Version"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("en_vigueur", "En vigueur"),
                            ("obsolete", "Obsolète"),
                        ],
                        default="brouillon",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "contenu",
                    models.TextField(
                        blank=True, default="", verbose_name="Contenu"
                    ),
                ),
                (
                    "document_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du document GED"
                    ),
                ),
                (
                    "date_application",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date d'entrée en vigueur"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "auteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_procedures_qualite",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auteur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_procedures_qualite",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Procédure qualité",
                "verbose_name_plural": "Procédures qualité",
                "ordering": ["reference", "-version", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="procedurequalite",
            index=models.Index(
                fields=["company", "reference"],
                name="qhse_procqual_co_ref",
            ),
        ),
        migrations.AddConstraint(
            model_name="procedurequalite",
            constraint=models.UniqueConstraint(
                fields=["company", "reference", "version"],
                name="qhse_procqual_ref_version_uniq",
            ),
        ),
    ]
