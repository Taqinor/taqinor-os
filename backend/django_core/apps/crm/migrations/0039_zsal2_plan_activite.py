# ZSAL2 — Plans d'activité (séquences de tâches pré-définies) : deux modèles
# additifs, PlanActivite + EtapePlanActivite. Aucune modification d'un modèle
# existant.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0005_alter_customuser_role"),
        ("records", "0007_comment_resolved"),
        ("crm", "0038_xfac23_client_delai_paiement"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanActivite",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=120)),
                ("actif", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="plans_activite", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Plan d'activité",
                "verbose_name_plural": "Plans d'activité",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="EtapePlanActivite",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("ordre", models.PositiveIntegerField(default=0)),
                ("delai_jours", models.PositiveIntegerField(
                    default=0,
                    help_text=(
                        "Nombre de jours après l'application du plan "
                        "(0 = le jour même)."
                    ))),
                ("resume_defaut", models.CharField(
                    blank=True, default="", max_length=255)),
                ("activity_type", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="etapes_plan_activite", to="records.activitytype")),
                ("assigne_par_defaut", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="etapes_plan_activite_assignees",
                    to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="etapes", to="crm.planactivite")),
            ],
            options={
                "verbose_name": "Étape de plan d'activité",
                "verbose_name_plural": "Étapes de plan d'activité",
                "ordering": ["plan", "ordre", "delai_jours"],
            },
        ),
    ]
