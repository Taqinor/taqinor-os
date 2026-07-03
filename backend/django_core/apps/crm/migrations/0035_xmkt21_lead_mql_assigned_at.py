# XMKT21 — Passage MQL automatique sur seuil de score : marqueur
# d'idempotence sur Lead. Additive + nullable, réversible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0034_qk1_lead_qualification"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="mql_assigned_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Horodatage de la première assignation automatique "
                          "déclenchée par le franchissement du seuil MQL "
                          "(XMKT21).",
                verbose_name="Assigné MQL le",
            ),
        ),
    ]
