"""Migration additive : création du modèle ``ClauseContrat``
(CONTRAT9 — clauses résolues, ordonnées, surchargeables d'un contrat).

Entièrement additive (``CreateModel`` + index + contrainte d'unicité partielle)
— réversible via ``DeleteModel``. La clause-source est optionnelle
(``on_delete=SET_NULL``) : supprimer une clause de la bibliothèque ne supprime
pas la clause résolue déjà matérialisée sur un contrat. L'unicité
``(contrat, clause)`` est CONDITIONNELLE (clause non nulle) : un contrat peut
porter plusieurs clauses ad hoc (``clause=NULL``). Index et contrainte nommés
explicitement (≤30 chars) pour éviter la divergence d'auto-nommage Django.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("contrats", "0007_clause_modelecontratclause"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClauseContrat",
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
                    "titre",
                    models.CharField(max_length=200, verbose_name="Titre"),
                ),
                (
                    "corps",
                    models.TextField(verbose_name="Corps résolu"),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
                ),
                (
                    "surchargee",
                    models.BooleanField(
                        default=False, verbose_name="Texte surchargé"
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
                        related_name="contrats_clauses_resolues",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clauses_resolues",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
                (
                    "clause",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contrats_clauses_resolues",
                        to="contrats.clause",
                        verbose_name="Clause source",
                    ),
                ),
            ],
            options={
                "verbose_name": "Clause du contrat",
                "verbose_name_plural": "Clauses du contrat",
                "ordering": ["contrat_id", "ordre", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="clausecontrat",
            index=models.Index(
                fields=["contrat", "ordre"],
                name="contrats_clausec_co_ordre",
            ),
        ),
        migrations.AddConstraint(
            model_name="clausecontrat",
            constraint=models.UniqueConstraint(
                fields=["contrat", "clause"],
                condition=models.Q(clause__isnull=False),
                name="contrats_clausecontrat_uniq",
            ),
        ),
    ]
