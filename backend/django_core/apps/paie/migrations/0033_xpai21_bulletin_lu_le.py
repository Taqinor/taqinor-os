# Generated manually — XPAI21 accusé de lecture du bulletin (coffre-fort
# employé, PAIE35) : horodate la première consultation, jamais réécrit.

from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI21 — BulletinPaie.lu_le (additif)."""

    dependencies = [
        ("paie", "0032_xpai20_provision_paie_mensuelle"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulletinpaie",
            name="lu_le",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Lu le (accusé de lecture)"),
        ),
    ]
