import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Contrat",
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
                    "type_contrat",
                    models.CharField(
                        choices=[
                            ("vente", "Vente"),
                            ("om", "O&M"),
                            ("monitoring", "Monitoring"),
                            ("garantie", "Garantie"),
                            ("ppa", "PPA"),
                            ("fournisseur", "Fournisseur"),
                            ("sous_traitance", "Sous-traitance"),
                            ("location", "Location"),
                            ("emploi", "Emploi"),
                            ("nda", "NDA"),
                            ("maintenance", "Maintenance"),
                            ("autre", "Autre"),
                        ],
                        default="vente",
                        max_length=20,
                        verbose_name="Type de contrat",
                    ),
                ),
                ("objet", models.CharField(max_length=255, verbose_name="Objet")),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("en_approbation", "En approbation"),
                            ("signe", "Signé"),
                            ("actif", "Actif"),
                            ("suspendu", "Suspendu"),
                            ("resilie", "Résilié"),
                            ("expire", "Expiré"),
                        ],
                        default="brouillon",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "client_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du client"
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de début"
                    ),
                ),
                (
                    "date_fin",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de fin"
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant",
                    ),
                ),
                (
                    "devise",
                    models.CharField(
                        default="MAD", max_length=3, verbose_name="Devise"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Contrat",
                "verbose_name_plural": "Contrats",
                "ordering": ["-id"],
            },
        ),
    ]
