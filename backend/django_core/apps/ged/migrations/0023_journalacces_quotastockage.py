# GED35 — Journal d'audit d'accès aux documents (lectures).
# GED36 — Quotas de stockage par société.
#
# Migration strictement ADDITIVE (réversible) : ajoute deux modèles indépendants.
#   * `JournalAcces` (GED35) trace chaque accès EN LECTURE à un document
#     (aperçu / téléchargement / public / consultation) ; append-only par
#     convention (aucune table existante n'est modifiée). Multi-tenant.
#   * `QuotaStockage` (GED36) fixe un quota de stockage (octets) PAR société
#     (OneToOne) ; l'usage courant est calculé à la volée (jamais dénormalisé).
# Aucune table existante n'est touchée — purement additif.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0022_demandesignaturedocument"),
    ]

    operations = [
        migrations.CreateModel(
            name="JournalAcces",
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
                    "type_acces",
                    models.CharField(
                        choices=[
                            ("apercu", "Aperçu"),
                            ("telechargement", "Téléchargement"),
                            ("public", "Accès public (lien)"),
                            ("consultation", "Consultation"),
                        ],
                        default="consultation",
                        max_length=14,
                        verbose_name="type d'accès",
                    ),
                ),
                (
                    "adresse_ip",
                    models.GenericIPAddressField(
                        blank=True, null=True, verbose_name="adresse IP"
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
                        related_name="ged_journaux_acces",
                        to="authentication.company",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acces",
                        to="ged.document",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_acces_documents",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="utilisateur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Accès au document (audit)",
                "verbose_name_plural": "Journal d'accès aux documents",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="QuotaStockage",
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
                    "quota_octets",
                    models.BigIntegerField(
                        default=0,
                        verbose_name="quota (octets, 0 = illimité)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_quota_stockage",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Quota de stockage GED",
                "verbose_name_plural": "Quotas de stockage GED",
            },
        ),
        migrations.AddIndex(
            model_name="journalacces",
            index=models.Index(
                fields=["company", "document"],
                name="ged_acces_co_doc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="journalacces",
            index=models.Index(
                fields=["company", "created_at"],
                name="ged_acces_co_date_idx",
            ),
        ),
    ]
