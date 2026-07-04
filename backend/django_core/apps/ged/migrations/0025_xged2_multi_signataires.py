# XGED2 — Circuit multi-signataires (séquentiel/parallèle) + relances +
# expiration + annulation.
#
# Migration strictement ADDITIVE (réversible) :
#   * ajoute `routage` / `relance_cadence_jours` / `annule_le` / `annule_par`
#     à `DemandeSignatureDocument` (GED30/XGED1) ;
#   * crée `SignataireDemande` (destinataires ordonnés d'une demande, chacun
#     avec son propre token public + statut individuel).
# Aucune table existante n'est retirée ni renommée. Rétrocompatible : le
# signataire mono-partie historique (`signataire_nom`/`signataire_email` sur
# la demande) reste affiché quand aucun `SignataireDemande` n'existe.
import apps.ged.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("ged", "0024_xged1_signature_ceremony"),
    ]

    operations = [
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="routage",
            field=models.CharField(
                choices=[
                    ("sequentiel", "Séquentiel (par ordre)"),
                    ("parallele", "Parallèle (tous en même temps)"),
                ],
                default="sequentiel",
                max_length=10,
                verbose_name="mode de routage",
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="relance_cadence_jours",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="cadence de relance (jours)"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="annule_le",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="annulée le"
            ),
        ),
        migrations.AddField(
            model_name="demandesignaturedocument",
            name="annule_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ged_demandes_signature_annulees",
                to=settings.AUTH_USER_MODEL,
                verbose_name="annulée par",
            ),
        ),
        migrations.CreateModel(
            name="SignataireDemande",
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
                ("nom", models.CharField(max_length=255, verbose_name="nom")),
                (
                    "email",
                    models.EmailField(
                        blank=True, default="", max_length=254, verbose_name="email"
                    ),
                ),
                (
                    "telephone",
                    models.CharField(
                        blank=True, default="", max_length=32, verbose_name="téléphone"
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=1, verbose_name="ordre"),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("signataire", "Signataire"),
                            ("copie", "Copie"),
                            ("approbateur", "Approbateur"),
                        ],
                        default="signataire",
                        max_length=12,
                        verbose_name="rôle",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente de son tour"),
                            ("notifie", "Notifié"),
                            ("signe", "Signé"),
                            ("refuse", "Refusé"),
                        ],
                        default="en_attente",
                        max_length=10,
                        verbose_name="statut",
                    ),
                ),
                (
                    "token",
                    models.CharField(
                        default=apps.ged.models._default_partage_token,
                        editable=False,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "notifie_le",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="notifié le"
                    ),
                ),
                (
                    "derniere_relance_le",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="dernière relance le"
                    ),
                ),
                (
                    "nb_relances",
                    models.PositiveIntegerField(
                        default=0, verbose_name="nombre de relances envoyées"
                    ),
                ),
                (
                    "date_action",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="signé/refusé le"
                    ),
                ),
                (
                    "motif_refus",
                    models.TextField(
                        blank=True, default="", verbose_name="motif de refus"
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
                        related_name="ged_signataires_demande",
                        to="authentication.company",
                    ),
                ),
                (
                    "demande",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signataires",
                        to="ged.demandesignaturedocument",
                    ),
                ),
            ],
            options={
                "verbose_name": "Signataire de demande",
                "verbose_name_plural": "Signataires de demande",
                "ordering": ["demande", "ordre", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="signatairedemande",
            index=models.Index(
                fields=["company", "demande"], name="ged_signataire_co_dem_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="signatairedemande",
            index=models.Index(
                fields=["demande", "ordre"], name="ged_signataire_dem_ordre_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="signatairedemande",
            index=models.Index(
                fields=["company", "statut"], name="ged_signataire_co_statut_idx"
            ),
        ),
    ]
