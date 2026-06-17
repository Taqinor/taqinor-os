import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("installations", "0005_installation_art33_regularisation_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="intervention",
            name="statut",
            field=models.CharField(
                choices=[
                    ("a_preparer", "À préparer"),
                    ("prete", "Prête"),
                    ("en_route", "En route"),
                    ("sur_site", "Sur site"),
                    ("terminee", "Terminée"),
                    ("validee", "Validée"),
                ],
                default="a_preparer",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="intervention",
            name="camionnette",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="intervention",
            name="equipe",
            field=models.ManyToManyField(
                blank=True,
                related_name="interventions_equipe",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="intervention",
            name="type_intervention",
            field=models.CharField(
                choices=[
                    ("pose", "Pose"),
                    ("raccordement", "Raccordement"),
                    ("mise_en_service", "Mise en service"),
                    ("controle", "Contrôle"),
                    ("depannage", "Dépannage"),
                    ("sav", "SAV"),
                    ("visite", "Visite"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="InterventionActivity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("creation", "Création"),
                            ("modification", "Modification"),
                            ("note", "Note"),
                        ],
                        max_length=15,
                    ),
                ),
                ("field", models.CharField(blank=True, max_length=100, null=True)),
                ("field_label", models.CharField(blank=True, max_length=150, null=True)),
                ("old_value", models.TextField(blank=True, null=True)),
                ("new_value", models.TextField(blank=True, null=True)),
                ("body", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intervention_activities",
                        to="authentication.company",
                    ),
                ),
                (
                    "intervention",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activites",
                        to="installations.intervention",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="intervention_activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Activité intervention",
                "verbose_name_plural": "Activités intervention",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="interventionactivity",
            index=models.Index(
                fields=["intervention", "-created_at"],
                name="installatio_interv_b6c8e6_idx",
            ),
        ),
    ]
