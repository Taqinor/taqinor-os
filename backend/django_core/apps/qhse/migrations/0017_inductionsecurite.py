# Generated for QHSE26 — Accueil / induction sécurité (accès site, sous-traitants)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0023_causerie_securite"),
        ("qhse", "0016_consignationloto"),
    ]

    operations = [
        migrations.CreateModel(
            name="InductionSecurite",
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
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du chantier",
                    ),
                ),
                (
                    "personne_nom",
                    models.CharField(
                        max_length=255, verbose_name="Personne accueillie"
                    ),
                ),
                (
                    "est_sous_traitant",
                    models.BooleanField(
                        default=False, verbose_name="Sous-traitant externe"
                    ),
                ),
                (
                    "entreprise_externe",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Entreprise externe",
                    ),
                ),
                (
                    "date_induction",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de l'accueil",
                    ),
                ),
                (
                    "anime_par",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Animé par",
                    ),
                ),
                (
                    "themes",
                    models.TextField(
                        blank=True, default="",
                        verbose_name="Thèmes couverts",
                    ),
                ),
                (
                    "acquittement",
                    models.BooleanField(
                        default=False,
                        verbose_name="Acquittement / signature",
                    ),
                ),
                (
                    "acquittement_le",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Acquitté le"
                    ),
                ),
                (
                    "validite_jours",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="Validité (jours)",
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
                        related_name="qhse_inductions_securite",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "employe",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_inductions_securite",
                        to="rh.dossieremploye",
                        verbose_name="Salarié (dossier RH)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Accueil sécurité (induction)",
                "verbose_name_plural": "Accueils sécurité (inductions)",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="inductionsecurite",
            index=models.Index(
                fields=["company", "chantier_id"],
                name="qhse_induc_co_chant",
            ),
        ),
        migrations.AddIndex(
            model_name="inductionsecurite",
            index=models.Index(
                fields=["company", "est_sous_traitant"],
                name="qhse_induc_co_stt",
            ),
        ),
        migrations.AddIndex(
            model_name="inductionsecurite",
            index=models.Index(
                fields=["company", "date_induction"],
                name="qhse_induc_co_date",
            ),
        ),
    ]
