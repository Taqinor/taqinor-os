# Generated for XFLT21 — Journal d'audit flotte. Crée ``ActiviteFlotte``
# (immuable, alimenté dans perform_update). Additif, multi-société.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("flotte", "0045_remiseaccessoire"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActiviteFlotte",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("type_objet", models.CharField(
                    choices=[
                        ("vehicule", "Véhicule"),
                        ("affectation", "Affectation conducteur"),
                    ], max_length=11, verbose_name="Type d'objet")),
                ("objet_id", models.PositiveIntegerField(
                    verbose_name="ID de l'objet")),
                ("champ", models.CharField(
                    max_length=60, verbose_name="Champ modifié")),
                ("ancienne_valeur", models.CharField(
                    blank=True, max_length=255,
                    verbose_name="Ancienne valeur")),
                ("nouvelle_valeur", models.CharField(
                    blank=True, max_length=255,
                    verbose_name="Nouvelle valeur")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_activites",
                    to="authentication.company", verbose_name="Société")),
                ("user", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="flotte_activites",
                    to=settings.AUTH_USER_MODEL, verbose_name="Utilisateur")),
                ("vehicule", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_activites", to="flotte.vehicule",
                    verbose_name="Véhicule")),
            ],
            options={
                "verbose_name": "Activité flotte (journal d'audit)",
                "verbose_name_plural": "Activités flotte (journal d'audit)",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="activiteflotte",
            index=models.Index(
                fields=["company", "vehicule"], name="flotte_act_co_veh_idx"),
        ),
        migrations.AddIndex(
            model_name="activiteflotte",
            index=models.Index(
                fields=["company", "type_objet", "objet_id"],
                name="flotte_act_co_type_obj_idx"),
        ),
    ]
