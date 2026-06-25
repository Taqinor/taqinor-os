# Generated for QJ1 — Proposal open-tracking on ShareLink.
# Additive only: three nullable / default=0 fields; no existing row is touched.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0029_fg52_devise_taux_change"),
    ]

    operations = [
        migrations.AddField(
            model_name="sharelink",
            name="first_viewed_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Première consultation",
            ),
        ),
        migrations.AddField(
            model_name="sharelink",
            name="last_viewed_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Dernière consultation",
            ),
        ),
        migrations.AddField(
            model_name="sharelink",
            name="view_count",
            field=models.PositiveIntegerField(
                default=0,
                verbose_name="Nombre de consultations",
            ),
        ),
    ]
