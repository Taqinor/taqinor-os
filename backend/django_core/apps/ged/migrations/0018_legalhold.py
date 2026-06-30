# GED24 — Rétention légale / legal hold (gel anti-suppression pour contentieux).
#
# Ajoute le modèle `LegalHold` (additif, réversible) : place un gel TEMPORAIRE
# de la suppression sur un document — typiquement pour un litige. Tant qu'un
# hold ACTIF couvre le document, sa suppression/purge est bloquée (garde côté
# application dans `Document.delete()` + services, traduite en 403 côté vue),
# surclassant toute purge de politique de rétention (GED22). À la différence de
# l'archivage légal (GED23, write-once permanent), un legal hold est levable
# (`actif=False` + trace `date_levee`/`leve_par`) et ne gèle QUE l'effacement.
# Multi-tenant (company FK). Aucune table existante n'est modifiée : migration
# strictement additive.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0017_archivagelegal"),
    ]

    operations = [
        migrations.CreateModel(
            name="LegalHold",
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
                    "motif",
                    models.TextField(blank=True, default="", verbose_name="motif"),
                ),
                (
                    "date_pose",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="placé le"
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="actif"),
                ),
                (
                    "date_levee",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="levé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_legal_holds",
                        to="authentication.company",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="legal_holds",
                        to="ged.document",
                    ),
                ),
                (
                    "place_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_legal_holds_poses",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="placé par",
                    ),
                ),
                (
                    "leve_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_legal_holds_leves",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="levé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Rétention légale (legal hold)",
                "verbose_name_plural": "Rétentions légales (legal holds)",
                "ordering": ["-date_pose", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="legalhold",
            index=models.Index(
                fields=["company", "document", "actif"],
                name="ged_hold_co_doc_actif_idx",
            ),
        ),
    ]
