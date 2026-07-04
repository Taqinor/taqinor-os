# Generated manually — ZRH4 jours de blocage congés (Mandatory/Stress Days).
# Additif, nouveau modèle.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH4 — JourBloqueConge (additif)."""

    dependencies = [
        ("rh", "0071_zrh2_solde_conge_accrual_guards"),
    ]

    operations = [
        migrations.CreateModel(
            name="JourBloqueConge",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(max_length=160, verbose_name="Libellé")),
                ("date_debut", models.DateField(verbose_name="Du")),
                ("date_fin", models.DateField(verbose_name="Au")),
                ("motif", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Motif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("date_modification", models.DateTimeField(
                    auto_now=True, verbose_name="Modifié le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_jours_bloques_conge",
                    to="authentication.company", verbose_name="Société")),
                ("departements", models.ManyToManyField(
                    blank=True, related_name="jours_bloques_conge",
                    to="rh.departement",
                    verbose_name="Départements concernés (vide = toute la "
                                 "société)")),
            ],
            options={
                "verbose_name": "Jour bloqué (congés)",
                "verbose_name_plural": "Jours bloqués (congés)",
                "ordering": ["-date_debut"],
            },
        ),
        migrations.AddIndex(
            model_name="jourbloqueconge",
            index=models.Index(
                fields=["company", "date_debut", "date_fin"],
                name="rh_jbc_comp_debut_fin_idx"),
        ),
    ]
