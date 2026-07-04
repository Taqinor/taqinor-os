# ZCTR1 — Plan de facturation récurrente réutilisable (RecurringPlan config).
# Nouveau modèle `PlanRecurrent` (company-scoped) + FK nullable
# `Contrat.plan_recurrent`. Purement additif : NULL partout = comportement
# actuel inchangé (périodicité lue sur l'échéancier local).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("contrats", "0033_xctr20_location_recurrente"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanRecurrent",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=120, verbose_name="Nom")),
                ("unite", models.CharField(
                    choices=[
                        ("mensuel", "Mensuel"),
                        ("trimestriel", "Trimestriel"),
                        ("semestriel", "Semestriel"),
                        ("annuel", "Annuel"),
                    ],
                    default="mensuel", max_length=15, verbose_name="Unité")),
                ("intervalle", models.PositiveIntegerField(
                    default=1, verbose_name="Intervalle")),
                ("delai_cloture_auto_jours", models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name="Délai de clôture auto (jours)")),
                ("aligner_debut_periode", models.BooleanField(
                    default=False,
                    verbose_name="Aligner sur le début de période")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="plans_recurrents",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Plan de facturation récurrente",
                "verbose_name_plural": "Plans de facturation récurrente",
                "ordering": ["nom", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="planrecurrent",
            index=models.Index(
                fields=["company", "actif"], name="contrats_planrec_co_act"),
        ),
        migrations.AddField(
            model_name="contrat",
            name="plan_recurrent",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="contrats",
                to="contrats.planrecurrent",
                verbose_name="Plan de facturation récurrente"),
        ),
    ]
