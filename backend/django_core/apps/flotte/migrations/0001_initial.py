import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Vehicule",
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
                    "immatriculation",
                    models.CharField(max_length=20, verbose_name="Immatriculation"),
                ),
                (
                    "marque",
                    models.CharField(
                        blank=True, default="", max_length=80, verbose_name="Marque"
                    ),
                ),
                (
                    "modele",
                    models.CharField(
                        blank=True, default="", max_length=80, verbose_name="Modèle"
                    ),
                ),
                (
                    "type_vehicule",
                    models.CharField(
                        choices=[
                            ("vehicule", "Véhicule léger"),
                            ("camionnette", "Camionnette"),
                            ("utilitaire", "Utilitaire"),
                            ("nacelle", "Nacelle"),
                            ("groupe_electrogene", "Groupe électrogène"),
                            ("chariot", "Chariot élévateur"),
                            ("autre", "Autre"),
                        ],
                        default="camionnette",
                        max_length=30,
                        verbose_name="Type de véhicule",
                    ),
                ),
                (
                    "energie",
                    models.CharField(
                        choices=[
                            ("essence", "Essence"),
                            ("diesel", "Diesel"),
                            ("electrique", "Électrique"),
                            ("hybride", "Hybride"),
                            ("gpl", "GPL"),
                        ],
                        default="diesel",
                        max_length=20,
                        verbose_name="Énergie",
                    ),
                ),
                (
                    "kilometrage",
                    models.PositiveIntegerField(default=0, verbose_name="Kilométrage"),
                ),
                (
                    "valeur_acquisition",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Valeur d'acquisition",
                    ),
                ),
                (
                    "date_mise_circulation",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de mise en circulation",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("actif", "Actif"),
                            ("maintenance", "En maintenance"),
                            ("hors_service", "Hors service"),
                            ("cede", "Cédé"),
                        ],
                        default="actif",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_vehicules",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "conducteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vehicules_conduits",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Conducteur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Véhicule",
                "verbose_name_plural": "Véhicules",
                "ordering": ["immatriculation"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="vehicule",
            unique_together={("company", "immatriculation")},
        ),
    ]
