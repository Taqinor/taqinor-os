# ZMKT16 - questions d'inscription par evenement (QuestionEvenement) +
# reponses_questions JSON sur InscriptionEvenement. Additif : JSON vide par
# defaut = comportement actuel (aucune question supplementaire).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0101_zmkt15_billet_evenement"),
    ]

    operations = [
        migrations.AddField(
            model_name="inscriptionevenement",
            name="reponses_questions",
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name="Réponses aux questions d'inscription (JSON)"),
        ),
        migrations.CreateModel(
            name="QuestionEvenement",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(
                    max_length=255, verbose_name="Libellé")),
                ("type_question", models.CharField(
                    choices=[
                        ("choix", "Choix"), ("texte", "Texte"),
                        ("booleen", "Booléen"),
                    ],
                    default="texte", max_length=10, verbose_name="Type")),
                ("obligatoire", models.BooleanField(
                    default=False, verbose_name="Obligatoire")),
                ("portee", models.CharField(
                    choices=[
                        ("par_inscrit", "Par inscrit"),
                        ("par_commande", "Par commande"),
                    ],
                    default="par_inscrit", max_length=15,
                    verbose_name="Portée")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="questions_evenement",
                    to="authentication.company", verbose_name="Société")),
                ("evenement", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="questions", to="compta.evenementmarketing",
                    verbose_name="Événement")),
            ],
            options={
                "verbose_name": "Question d'inscription (événement)",
                "verbose_name_plural": "Questions d'inscription (événement)",
                "ordering": ["id"],
            },
        ),
    ]
