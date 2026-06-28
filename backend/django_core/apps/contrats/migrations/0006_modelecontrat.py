"""Migration additive : création du modèle ``ModeleContrat`` (CONTRAT7).

Bibliothèque de gabarits/modèles de contrats réutilisables. Entièrement
additive (``CreateModel``) — réversible via ``DeleteModel``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("contrats", "0005_contrat_confidentialite"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeleContrat",
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
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contrats_modeles",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "nom",
                    models.CharField(max_length=200, verbose_name="Nom du modèle"),
                ),
                (
                    "categorie",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=100,
                        verbose_name="Catégorie",
                    ),
                ),
                (
                    "type_contrat_defaut",
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
                        verbose_name="Type de contrat par défaut",
                    ),
                ),
                (
                    "corps",
                    models.TextField(
                        blank=True, default="", verbose_name="Corps du contrat"
                    ),
                ),
                (
                    "clauses",
                    models.TextField(
                        blank=True, default="", verbose_name="Clauses types"
                    ),
                ),
                (
                    "devise_defaut",
                    models.CharField(
                        default="MAD", max_length=3, verbose_name="Devise par défaut"
                    ),
                ),
                (
                    "confidentialite_defaut",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("interne", "Interne"),
                            ("confidentiel", "Confidentiel"),
                        ],
                        default="interne",
                        max_length=20,
                        verbose_name="Confidentialité par défaut",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
            ],
            options={
                "verbose_name": "Modèle de contrat",
                "verbose_name_plural": "Modèles de contrats",
                "ordering": ["ordre", "nom"],
            },
        ),
    ]
