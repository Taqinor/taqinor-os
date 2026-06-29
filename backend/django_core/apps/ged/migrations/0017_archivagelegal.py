# GED23 — Archivage légal à valeur probante (write-once / object-lock).
#
# Ajoute le modèle `ArchivageLegal` (additif, réversible) : marque un document
# comme archivé légalement → le document (et ses versions) devient IMMUABLE
# (write-once, garanti côté application dans les modèles + services). On fige un
# `hash_integrite` (SHA-256 hex, 64 caractères) de la version archivée pour la
# valeur probante, et — en BONUS best-effort — une date de verrou objet
# (object-lock retain-until). L'enregistrement est unique par document
# (write-once) et immuable (création seule). Multi-tenant (company FK). Aucune
# table existante n'est modifiée : migration strictement additive.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0016_politiqueretention"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArchivageLegal",
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
                    "archive_le",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="archivé le"
                    ),
                ),
                (
                    "motif",
                    models.TextField(blank=True, default="", verbose_name="motif"),
                ),
                (
                    "hash_integrite",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=64,
                        verbose_name="condensat d'intégrité (SHA-256)",
                    ),
                ),
                (
                    "object_lock_retain_until",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="verrou objet jusqu'au",
                    ),
                ),
                (
                    "object_lock_applique",
                    models.BooleanField(
                        default=False, verbose_name="verrou objet appliqué"
                    ),
                ),
                (
                    "archive_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_archivages_legaux",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="archivé par",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_archivages_legaux",
                        to="authentication.company",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="archivages_legaux",
                        to="ged.document",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="archivages_legaux",
                        to="ged.documentversion",
                        verbose_name="version archivée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Archivage légal",
                "verbose_name_plural": "Archivages légaux",
                "ordering": ["-archive_le", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="archivagelegal",
            index=models.Index(
                fields=["company", "document"], name="ged_arch_legal_co_doc_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="archivagelegal",
            constraint=models.UniqueConstraint(
                fields=["document"], name="ged_arch_legal_doc_unique"
            ),
        ),
    ]
