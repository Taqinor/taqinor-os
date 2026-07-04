# Generated for XFLT15 — Analyse de remplacement (fin de vie économique).
# Crée ``ParametreRemplacementFlotte`` (seuils éditables par société).
# Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0039_garantieflotte"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametreRemplacementFlotte",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("age_max_ans", models.PositiveSmallIntegerField(
                    default=8, verbose_name="Âge maximal (ans)")),
                ("km_max", models.PositiveIntegerField(
                    default=200000, verbose_name="Kilométrage maximal")),
                ("ratio_cout_reparation_max", models.DecimalField(
                    decimal_places=2, default=0.30, max_digits=4,
                    verbose_name="Ratio coût-réparations/valeur vénale max")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_parametre_remplacement",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Paramètre de remplacement flotte",
                "verbose_name_plural": "Paramètres de remplacement flotte",
            },
        ),
    ]
