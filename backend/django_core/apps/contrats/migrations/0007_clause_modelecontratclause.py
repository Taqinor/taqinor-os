"""Migration additive : création des modèles ``Clause`` et ``ModeleContratClause``
(CONTRAT8 — bibliothèque de clauses réutilisables).

Entièrement additive (``CreateModel`` x2) — réversible via ``DeleteModel``.
Index nommés explicitement (≤30 chars) pour éviter la divergence entre
l'auto-nommage Django et le nom stocké en migration.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("contrats", "0006_modelecontrat"),
    ]

    operations = [
        migrations.CreateModel(
            name="Clause",
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
                        related_name="contrats_clauses",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "titre",
                    models.CharField(max_length=200, verbose_name="Titre"),
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
                    "type_clause",
                    models.CharField(
                        choices=[
                            ("generale", "Générale"),
                            ("technique", "Technique"),
                            ("financiere", "Financière"),
                            ("juridique", "Juridique"),
                            ("resiliation", "Résiliation"),
                            ("garantie", "Garantie"),
                            ("confidentialite", "Confidentialité"),
                            ("autre", "Autre"),
                        ],
                        default="generale",
                        max_length=20,
                        verbose_name="Type de clause",
                    ),
                ),
                (
                    "corps",
                    models.TextField(verbose_name="Corps de la clause"),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
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
            ],
            options={
                "verbose_name": "Clause",
                "verbose_name_plural": "Clauses",
                "ordering": ["ordre", "titre"],
            },
        ),
        migrations.AddIndex(
            model_name="clause",
            index=models.Index(
                fields=["company", "actif"],
                name="contrats_clause_co_actif",
            ),
        ),
        migrations.AddIndex(
            model_name="clause",
            index=models.Index(
                fields=["company", "type_clause"],
                name="contrats_clause_co_type",
            ),
        ),
        migrations.CreateModel(
            name="ModeleContratClause",
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
                        related_name="contrats_modele_clauses",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "modele",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="modele_clauses",
                        to="contrats.modelecontrat",
                        verbose_name="Modèle de contrat",
                    ),
                ),
                (
                    "clause",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="modele_clauses",
                        to="contrats.clause",
                        verbose_name="Clause",
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
                ),
            ],
            options={
                "verbose_name": "Clause du modèle",
                "verbose_name_plural": "Clauses du modèle",
                "ordering": ["modele_id", "ordre", "id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="modelecontratclause",
            unique_together={("modele", "clause")},
        ),
        migrations.AddIndex(
            model_name="modelecontratclause",
            index=models.Index(
                fields=["modele", "ordre"],
                name="contrats_mc_clause_modele",
            ),
        ),
    ]
