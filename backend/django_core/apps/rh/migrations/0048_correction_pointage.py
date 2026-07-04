# XRH11 — Audit immuable des corrections de pointage.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rh", "0047_kiosque_pointage"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorrectionPointage",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("champ", models.CharField(max_length=60)),
                ("ancienne_valeur", models.TextField(blank=True, default="")),
                ("nouvelle_valeur", models.TextField(blank=True, default="")),
                ("motif", models.CharField(max_length=255)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("auteur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rh_corrections_pointage",
                    to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_corrections_pointage",
                    to="authentication.company")),
                ("pointage", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="corrections", to="rh.pointage")),
            ],
            options={
                "verbose_name": "Correction de pointage",
                "verbose_name_plural": "Corrections de pointage",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="correctionpointage",
            index=models.Index(
                fields=["pointage", "-date_creation"],
                name="rh_correction_pt_date_idx"),
        ),
    ]
