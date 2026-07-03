# XRH21 — Vivier de candidats (talent pool).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0057_promesse_embauche"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidature",
            name="vivier",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="candidature",
            name="tags_vivier",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="candidature",
            name="vivier_origine",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rattachements", to="rh.candidature"),
        ),
    ]
