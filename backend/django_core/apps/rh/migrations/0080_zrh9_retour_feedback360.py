# Generated manually — ZRH9 feedback 360° (avis multi-sources sur un entretien).
# Additif, nouveau modèle.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH9 — RetourFeedback360 (additif)."""

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("rh", "0079_zrh10_historique_competence"),
    ]

    operations = [
        migrations.CreateModel(
            name="RetourFeedback360",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("relation", models.CharField(
                    choices=[
                        ("pair", "Pair"),
                        ("subordonne", "Subordonné"),
                        ("manager_transversal", "Manager transversal"),
                    ],
                    default="pair", max_length=20,
                    verbose_name="Relation")),
                ("reponses", models.JSONField(
                    blank=True, default=dict, verbose_name="Réponses")),
                ("commentaire", models.TextField(
                    blank=True, default="", verbose_name="Commentaire")),
                ("soumis", models.BooleanField(
                    default=False, verbose_name="Soumis")),
                ("date_invitation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Date d'invitation")),
                ("date_soumission", models.DateTimeField(
                    blank=True, null=True,
                    verbose_name="Date de soumission")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_retours_feedback360",
                    to="authentication.company", verbose_name="Société")),
                ("evaluation", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="retours_360",
                    to="rh.evaluationemploye", verbose_name="Évaluation")),
                ("repondant", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="retours_feedback360",
                    to="rh.dossieremploye", verbose_name="Répondant")),
            ],
            options={
                "verbose_name": "Retour feedback 360°",
                "verbose_name_plural": "Retours feedback 360°",
                "ordering": ["-date_invitation"],
            },
        ),
        migrations.AddConstraint(
            model_name="retourfeedback360",
            constraint=models.UniqueConstraint(
                fields=("evaluation", "repondant"),
                name="rh_feedback360_eval_repondant_uniq"),
        ),
        migrations.AddIndex(
            model_name="retourfeedback360",
            index=models.Index(
                fields=["company", "evaluation"],
                name="rh_feedback360_comp_eval_idx"),
        ),
    ]
