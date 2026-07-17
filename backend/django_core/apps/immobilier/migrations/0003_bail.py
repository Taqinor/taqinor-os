# Hand-authored (NTPRO3) — see 0001_initial.py header for why manage.py
# makemigrations cannot run in this host env (Django 6.0.6 vs pinned 5.1.4).
# NTPRO5 adds six more fields to Bail in migration 0005 (depot de garantie).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("immobilier", "0002_locataire"),
    ]

    operations = [
        migrations.CreateModel(
            name="Bail",
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
                    "type_bail",
                    models.CharField(
                        choices=[
                            ("habitation", "Habitation (loi 67-12)"),
                            ("commercial", "Commercial (loi 49-16)"),
                        ],
                        default="habitation",
                        max_length=12,
                        verbose_name="Type de bail",
                    ),
                ),
                ("date_debut", models.DateField(verbose_name="Date de début")),
                (
                    "duree_mois",
                    models.PositiveIntegerField(verbose_name="Durée (mois)"),
                ),
                (
                    "loyer_mensuel_ht",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        verbose_name="Loyer mensuel HT",
                    ),
                ),
                (
                    "charges_mensuelles_provisions",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        verbose_name="Charges mensuelles (provisions)",
                    ),
                ),
                (
                    "depot_garantie",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        verbose_name="Dépôt de garantie",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("actif", "Actif"),
                            ("preavis", "Préavis"),
                            ("resilie", "Résilié"),
                            ("expire", "Expiré"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_preavis",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de préavis"
                    ),
                ),
                (
                    "date_fin_effective",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de fin effective",
                    ),
                ),
                (
                    "bailleur_nom_snapshot",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Bailleur (snapshot)",
                    ),
                ),
                (
                    "locataire_nom_snapshot",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Locataire (snapshot)",
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_baux",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "local",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="baux",
                        to="immobilier.local",
                        verbose_name="Local",
                    ),
                ),
                (
                    "locataire",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="baux",
                        to="immobilier.locataire",
                        verbose_name="Locataire",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bail",
                "verbose_name_plural": "Baux",
                "ordering": ["-date_debut", "-id"],
            },
        ),
    ]
