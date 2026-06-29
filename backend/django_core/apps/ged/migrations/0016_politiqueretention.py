# GED22 — Politiques de rétention documentaire.
#
# Ajoute le modèle `PolitiqueRetention` (additif, réversible) : durée de
# conservation par classe de documents + action à l'échéance. L'action est par
# défaut « signaler » (purement consultative) ; la rétention ne supprime JAMAIS
# rien passivement (jamais destructif par défaut). Multi-tenant (company FK).
# Aucune table existante n'est modifiée : migration strictement additive.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0015_ged21_watermark"),
    ]

    operations = [
        migrations.CreateModel(
            name="PolitiqueRetention",
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
                ("nom", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "type_document",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=80,
                        verbose_name="catégorie de document",
                    ),
                ),
                (
                    "duree_conservation_jours",
                    models.PositiveIntegerField(
                        verbose_name="durée de conservation (jours)"
                    ),
                ),
                (
                    "action_echeance",
                    models.CharField(
                        choices=[
                            ("signaler", "Signaler"),
                            ("archiver", "Archiver"),
                            ("supprimer", "Supprimer"),
                        ],
                        default="signaler",
                        max_length=10,
                        verbose_name="action à l'échéance",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="active"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cabinet",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="politiques_retention",
                        to="ged.cabinet",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_politiques_retention",
                        to="authentication.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_politiques_retention_crees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "folder",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="politiques_retention",
                        to="ged.folder",
                    ),
                ),
            ],
            options={
                "verbose_name": "Politique de rétention GED",
                "verbose_name_plural": "Politiques de rétention GED",
                "ordering": ["nom", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="politiqueretention",
            index=models.Index(
                fields=["company", "actif"], name="ged_retention_co_actif_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="politiqueretention",
            index=models.Index(
                fields=["company", "cabinet"], name="ged_retention_co_cab_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="politiqueretention",
            index=models.Index(
                fields=["company", "folder"], name="ged_retention_co_fol_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="politiqueretention",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(cabinet__isnull=True)
                    | models.Q(folder__isnull=True)
                ),
                name="ged_retention_cab_xor_folder",
            ),
        ),
    ]
