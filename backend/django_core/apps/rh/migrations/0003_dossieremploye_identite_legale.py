# Generated for FG156 — Moroccan payroll identity & legal numbers on
# DossierEmploye (CNSS/CIMR/AMO, situation familiale, nombre d'enfants).
# All additive, optional/blank with safe defaults, no unique constraint — so
# existing employee rows stay valid (no AddField(unique, default) trap).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0002_dossieremploye_contrat_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="dossieremploye",
            name="cnss",
            field=models.CharField(
                blank=True, default="", max_length=20, verbose_name="N° CNSS"
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="cimr",
            field=models.CharField(
                blank=True, default="", max_length=20, verbose_name="N° CIMR"
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="amo",
            field=models.CharField(
                blank=True, default="", max_length=20, verbose_name="N° AMO"
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="situation_familiale",
            field=models.CharField(
                blank=True,
                choices=[
                    ("celibataire", "Célibataire"),
                    ("marie", "Marié(e)"),
                    ("divorce", "Divorcé(e)"),
                    ("veuf", "Veuf(ve)"),
                ],
                default="",
                max_length=12,
                verbose_name="Situation familiale",
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="nombre_enfants",
            field=models.PositiveIntegerField(
                default=0, verbose_name="Nombre d'enfants"
            ),
        ),
    ]
