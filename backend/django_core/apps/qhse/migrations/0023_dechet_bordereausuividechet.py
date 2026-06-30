# Generated for QHSE36 — Déchet + BordereauSuiviDechet (BSD, loi 28-00).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0022_inspectionsecurite"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dechet",
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
                ("libelle", models.CharField(max_length=255, verbose_name="Libellé")),
                (
                    "code",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Code déchet",
                    ),
                ),
                (
                    "categorie",
                    models.CharField(
                        choices=[
                            ("dangereux", "Dangereux"),
                            ("non_dangereux", "Non dangereux"),
                            ("inerte", "Inerte"),
                        ],
                        default="non_dangereux",
                        max_length=15,
                        verbose_name="Catégorie",
                    ),
                ),
                (
                    "unite",
                    models.CharField(
                        blank=True,
                        default="kg",
                        max_length=20,
                        verbose_name="Unité",
                    ),
                ),
                (
                    "mode_traitement",
                    models.CharField(
                        choices=[
                            ("recyclage", "Recyclage / valorisation"),
                            ("enfouissement", "Enfouissement"),
                            ("incineration", "Incinération"),
                            ("traitement_specialise", "Traitement spécialisé"),
                            ("autre", "Autre"),
                        ],
                        default="recyclage",
                        max_length=25,
                        verbose_name="Mode de traitement",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
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
                        related_name="qhse_dechets",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Déchet",
                "verbose_name_plural": "Déchets",
                "ordering": ["libelle", "id"],
            },
        ),
        migrations.CreateModel(
            name="BordereauSuiviDechet",
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
                        blank=True,
                        default="",
                        max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("emis", "Émis"),
                            ("enleve", "Enlevé"),
                            ("traite", "Traité"),
                            ("annule", "Annulé"),
                        ],
                        default="emis",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID du chantier producteur",
                    ),
                ),
                (
                    "quantite",
                    models.DecimalField(
                        blank=True,
                        decimal_places=3,
                        max_digits=12,
                        null=True,
                        verbose_name="Quantité",
                    ),
                ),
                (
                    "producteur",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Producteur",
                    ),
                ),
                (
                    "transporteur",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Transporteur",
                    ),
                ),
                (
                    "eliminateur",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Éliminateur",
                    ),
                ),
                (
                    "date_emission",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'émission"
                    ),
                ),
                (
                    "date_enlevement",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'enlèvement"
                    ),
                ),
                (
                    "date_traitement",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de traitement"
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
                        related_name="qhse_bsd",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "dechet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bordereaux",
                        to="qhse.dechet",
                        verbose_name="Déchet",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bordereau de suivi des déchets",
                "verbose_name_plural": "Bordereaux de suivi des déchets",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="dechet",
            index=models.Index(
                fields=["company", "categorie"], name="qhse_dechet_co_cat"
            ),
        ),
        migrations.AddConstraint(
            model_name="bordereausuividechet",
            constraint=models.UniqueConstraint(
                fields=("company", "reference"), name="qhse_bsd_co_ref_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="bordereausuividechet",
            index=models.Index(
                fields=["company", "statut"], name="qhse_bsd_co_statut"
            ),
        ),
        migrations.AddIndex(
            model_name="bordereausuividechet",
            index=models.Index(
                fields=["company", "chantier_id"], name="qhse_bsd_co_chant"
            ),
        ),
    ]
