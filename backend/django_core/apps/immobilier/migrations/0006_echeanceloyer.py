# Hand-authored (NTPRO6) — see 0001_initial.py header for why manage.py
# makemigrations cannot run in this host env (Django 6.0.6 vs pinned 5.1.4).
# facture_ventes_id/date_emission_quittance are included here (not a later
# migration) so NTPRO7 needs zero schema change (its Files: list has no
# models.py — it only wires services.py/pdf.py/views.py).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("immobilier", "0005_bail_depot_garantie"),
    ]

    operations = [
        migrations.CreateModel(
            name="EcheanceLoyer",
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
                    "periode_debut",
                    models.DateField(verbose_name="Début de période"),
                ),
                ("periode_fin", models.DateField(verbose_name="Fin de période")),
                (
                    "montant_loyer_ht",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        verbose_name="Montant loyer HT",
                    ),
                ),
                (
                    "montant_charges",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        verbose_name="Montant charges",
                    ),
                ),
                (
                    "montant_total",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        verbose_name="Montant total",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_emettre", "À émettre"),
                            ("emise", "Émise"),
                            ("payee", "Payée"),
                            ("impayee", "Impayée"),
                            ("relancee", "Relancée"),
                        ],
                        default="a_emettre",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "facture_ventes_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID facture ventes"
                    ),
                ),
                (
                    "date_emission_quittance",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Date d'émission de la quittance",
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "bail",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="echeances",
                        to="immobilier.bail",
                        verbose_name="Bail",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_echeances_loyer",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Échéance de loyer",
                "verbose_name_plural": "Échéances de loyer",
                "ordering": ["-periode_debut", "-id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="echeanceloyer",
            unique_together={("bail", "periode_debut")},
        ),
    ]
