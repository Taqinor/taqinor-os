# XRH16 — Grille salariale par poste (bandes min/max, compa-ratio).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0052_competence_requise"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrilleSalariale",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("echelon", models.CharField(
                    blank=True, default="", max_length=40)),
                ("salaire_min", models.DecimalField(
                    decimal_places=2, max_digits=14)),
                ("salaire_max", models.DecimalField(
                    decimal_places=2, max_digits=14)),
                ("date_effet", models.DateField()),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_grilles_salariales",
                    to="authentication.company")),
                ("poste", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="grilles_salariales", to="rh.poste")),
            ],
            options={
                "verbose_name": "Grille salariale",
                "verbose_name_plural": "Grilles salariales",
                "ordering": ["poste", "echelon", "-date_effet"],
            },
        ),
        migrations.AddIndex(
            model_name="grillesalariale",
            index=models.Index(
                fields=["company", "poste"],
                name="rh_grille_comp_poste_idx"),
        ),
    ]
