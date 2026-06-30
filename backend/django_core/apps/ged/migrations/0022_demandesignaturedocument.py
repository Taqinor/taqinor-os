# GED30 — Signature électronique (point d'intégration + STUB no-op).
#
# Ajoute le modèle `DemandeSignatureDocument` (additif, réversible) : un point
# d'intégration générique pour demander une signature électronique sur N'IMPORTE
# quel document GED et en suivre le statut. KEY-GATED no-op (mirroir de
# l'embedding GED12) : tant qu'aucun fournisseur e-sign externe n'est configuré
# (`settings.ESIGN_ENABLED` faux), la demande est un STUB purement LOCAL
# `en_attente` — aucun appel réseau, aucun coût, aucune dépendance nouvelle.
# Couche GÉNÉRIQUE distincte de la signature des CONTRATS
# (`contrats.SignatureContrat`, CONTRAT16) et du funnel `STAGES.py` (rule #2).
# Multi-tenant (company FK). Aucune table existante n'est modifiée : migration
# strictement additive.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0021_modeledocument_classement"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandeSignatureDocument",
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
                    "signataire_nom",
                    models.CharField(
                        max_length=255, verbose_name="nom du signataire"
                    ),
                ),
                (
                    "signataire_email",
                    models.EmailField(
                        max_length=254, verbose_name="email du signataire"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("signe", "Signée"),
                            ("refuse", "Refusée"),
                            ("annule", "Annulée"),
                        ],
                        default="en_attente",
                        max_length=10,
                        verbose_name="statut de la signature",
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        default="aucun",
                        max_length=40,
                        verbose_name="fournisseur e-sign",
                    ),
                ),
                (
                    "provider_ref",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="référence fournisseur",
                    ),
                ),
                (
                    "date_demande",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="demandée le"
                    ),
                ),
                (
                    "date_signature",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="signée le"
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
                        related_name="ged_demandes_signature",
                        to="authentication.company",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="demandes_signature",
                        to="ged.document",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_demandes_signature_creees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Demande de signature",
                "verbose_name_plural": "Demandes de signature",
                "ordering": ["-date_demande", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="demandesignaturedocument",
            index=models.Index(
                fields=["company", "document"],
                name="ged_sign_co_doc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="demandesignaturedocument",
            index=models.Index(
                fields=["company", "statut"],
                name="ged_sign_co_statut_idx",
            ),
        ),
    ]
