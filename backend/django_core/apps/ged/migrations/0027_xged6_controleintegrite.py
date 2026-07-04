# XGED6 — Vérification périodique d'intégrité des archives légales + dossier
# de preuve (loi 43-20).
#
# Migration strictement ADDITIVE (réversible) : crée `ControleIntegrite`, le
# journal append-only des contrôles périodiques d'un `ArchivageLegal` (GED23)
# — hash constaté, résultat (intègre/altéré/indisponible), horodatage.
# Aucune table existante n'est retirée ni renommée.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("ged", "0026_xged3_champsignature"),
    ]

    operations = [
        migrations.CreateModel(
            name="ControleIntegrite",
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
                    "resultat",
                    models.CharField(
                        choices=[
                            ("ok", "Intègre"),
                            ("altere", "Altéré"),
                            ("indisponible", "Indisponible"),
                        ],
                        default="ok",
                        max_length=14,
                        verbose_name="résultat",
                    ),
                ),
                (
                    "hash_constate",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="hash constaté (SHA-256)",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_controles_integrite",
                        to="authentication.company",
                    ),
                ),
                (
                    "archivage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="controles",
                        to="ged.archivagelegal",
                    ),
                ),
            ],
            options={
                "verbose_name": "Contrôle d'intégrité",
                "verbose_name_plural": "Contrôles d'intégrité",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="controleintegrite",
            index=models.Index(
                fields=["company", "archivage"], name="ged_ctrl_co_arch_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="controleintegrite",
            index=models.Index(
                fields=["company", "resultat"], name="ged_ctrl_co_resultat_idx"
            ),
        ),
    ]
