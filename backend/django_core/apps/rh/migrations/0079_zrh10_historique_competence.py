# Generated manually — ZRH10 historique des changements de niveau de compétence.
# Additif, nouveau modèle.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH10 — HistoriqueCompetence (additif)."""

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("rh", "0078_zrh15_ligne_parcours"),
    ]

    operations = [
        migrations.CreateModel(
            name="HistoriqueCompetence",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("ancien_niveau", models.PositiveSmallIntegerField(
                    verbose_name="Ancien niveau")),
                ("nouveau_niveau", models.PositiveSmallIntegerField(
                    verbose_name="Nouveau niveau")),
                ("source", models.CharField(
                    choices=[
                        ("manuelle", "Manuelle"),
                        ("quiz", "Quiz de formation"),
                        ("formation", "Session de formation"),
                    ],
                    default="manuelle", max_length=12,
                    verbose_name="Source")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_historiques_competence",
                    to="authentication.company", verbose_name="Société")),
                ("competence", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="historique",
                    to="rh.competence", verbose_name="Compétence")),
                ("employe", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="historique_competences",
                    to="rh.dossieremploye", verbose_name="Employé")),
            ],
            options={
                "verbose_name": "Historique de compétence",
                "verbose_name_plural": "Historiques de compétence",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="historiquecompetence",
            index=models.Index(
                fields=["company", "employe", "competence"],
                name="rh_hist_comp_emp_comp_idx"),
        ),
    ]
