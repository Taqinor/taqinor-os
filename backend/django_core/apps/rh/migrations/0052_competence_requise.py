# XRH15 — Compétences requises par poste + analyse d'écart.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0051_periode_fermeture"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetenceRequise",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("niveau_requis", models.PositiveSmallIntegerField(
                    choices=[
                        (0, "Non acquis"), (1, "Débutant"),
                        (2, "Intermédiaire"), (3, "Confirmé"),
                        (4, "Expert")],
                    default=2)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_competences_requises",
                    to="authentication.company")),
                ("competence", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="requise_pour_postes", to="rh.competence")),
                ("poste", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="competences_requises", to="rh.poste")),
            ],
            options={
                "verbose_name": "Compétence requise",
                "verbose_name_plural": "Compétences requises",
                "ordering": ["poste", "competence"],
            },
        ),
        migrations.AddConstraint(
            model_name="competencerequise",
            constraint=models.UniqueConstraint(
                fields=("poste", "competence"),
                name="rh_competence_requise_uniq"),
        ),
    ]
