# Generated manually — ZRH7 gabarits de questions d'évaluation réutilisables.
# Additif, nouveau modèle + FK/JSONField additifs.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH7 — ModeleEvaluation + CampagneEvaluation.modele +
    EvaluationEmploye.reponses (additif)."""

    dependencies = [
        ("rh", "0073_zrh5_cloture_pointages_ouverts"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeleEvaluation",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=160, verbose_name="Nom")),
                ("questions", models.JSONField(
                    blank=True, default=list, verbose_name="Questions")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("date_modification", models.DateTimeField(
                    auto_now=True, verbose_name="Modifié le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_modeles_evaluation",
                    to="authentication.company", verbose_name="Société")),
                ("departement", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="modeles_evaluation", to="rh.departement",
                    verbose_name="Département (cible)")),
                ("poste_ref", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="modeles_evaluation", to="rh.poste",
                    verbose_name="Poste (cible)")),
            ],
            options={
                "verbose_name": "Modèle d'évaluation",
                "verbose_name_plural": "Modèles d'évaluation",
                "ordering": ["nom"],
            },
        ),
        migrations.AddIndex(
            model_name="modeleevaluation",
            index=models.Index(
                fields=["company", "departement"],
                name="rh_modeval_comp_dep_idx"),
        ),
        migrations.AddField(
            model_name="campagneevaluation",
            name="modele",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="campagnes", to="rh.modeleevaluation",
                verbose_name="Modèle d'évaluation"),
        ),
        migrations.AddField(
            model_name="evaluationemploye",
            name="reponses",
            field=models.JSONField(
                blank=True, default=list, verbose_name="Réponses (modèle)"),
        ),
    ]
