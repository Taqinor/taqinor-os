# XRH18 — Chatter candidature + détection de doublons.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rh", "0054_entretien_recrutement"),
    ]

    operations = [
        migrations.CreateModel(
            name="CandidatureActivity",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("type", models.CharField(
                    choices=[("log", "Transition"), ("note", "Note")],
                    max_length=10)),
                ("field", models.CharField(
                    blank=True, default="", max_length=100)),
                ("old_value", models.TextField(blank=True, default="")),
                ("new_value", models.TextField(blank=True, default="")),
                ("message", models.TextField(blank=True, default="")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("auteur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rh_candidature_activites",
                    to=settings.AUTH_USER_MODEL)),
                ("candidature", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="activites", to="rh.candidature")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_candidature_activites",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Activité candidature",
                "verbose_name_plural": "Activités candidature",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="candidatureactivity",
            index=models.Index(
                fields=["candidature", "-date_creation"],
                name="rh_cand_act_cand_date_idx"),
        ),
    ]
