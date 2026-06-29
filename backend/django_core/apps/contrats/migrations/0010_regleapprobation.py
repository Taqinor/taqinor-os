"""Migration additive : création du modèle ``RegleApprobation``
(CONTRAT13 — règle d'approbation par seuil de montant et/ou type de contrat).

Entièrement additive (``CreateModel`` + index) — réversible via ``DeleteModel``.
Modèle data-driven : un intervalle de montant ``[montant_min, montant_max]``
(bornes optionnelles, NULL = ouvertes) et un ``type_contrat`` ciblé optionnel
décrivent quand la règle s'applique ; ``niveau_approbation`` /
``nombre_approbateurs`` portent l'exigence. Aucun seuil n'est codé en dur. Les
index sont nommés explicitement (≤30 chars) pour éviter la divergence
d'auto-nommage Django.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("contrats", "0009_contrat_modele"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegleApprobation",
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
                    "libelle",
                    models.CharField(max_length=200, verbose_name="Libellé"),
                ),
                (
                    "type_contrat",
                    models.CharField(
                        blank=True,
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
                        default="",
                        max_length=20,
                        verbose_name="Type de contrat ciblé",
                    ),
                ),
                (
                    "montant_min",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=14,
                        null=True,
                        verbose_name="Montant minimum",
                    ),
                ),
                (
                    "montant_max",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=14,
                        null=True,
                        verbose_name="Montant maximum",
                    ),
                ),
                (
                    "niveau_approbation",
                    models.CharField(
                        choices=[
                            ("responsable", "Responsable"),
                            ("administrateur", "Administrateur"),
                            ("direction", "Direction"),
                        ],
                        default="responsable",
                        max_length=20,
                        verbose_name="Niveau d'approbation requis",
                    ),
                ),
                (
                    "nombre_approbateurs",
                    models.PositiveIntegerField(
                        default=1,
                        verbose_name="Nombre d'approbateurs requis",
                    ),
                ),
                (
                    "priorite",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Priorité"
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
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
                        related_name="contrats_regles_approbation",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Règle d'approbation",
                "verbose_name_plural": "Règles d'approbation",
                "ordering": ["-priorite", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="regleapprobation",
            index=models.Index(
                fields=["company", "actif"],
                name="contrats_regleapp_co_act",
            ),
        ),
        migrations.AddIndex(
            model_name="regleapprobation",
            index=models.Index(
                fields=["company", "type_contrat"],
                name="contrats_regleapp_co_typ",
            ),
        ),
    ]
