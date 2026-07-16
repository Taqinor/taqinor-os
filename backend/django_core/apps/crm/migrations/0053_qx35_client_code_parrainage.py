# QX35 — Wire the parrainage promise. Additive, nullable, unique referral
# code on Client (deterministic, derived from pk on first save — see
# Client.save()). Existing rows stay NULL until resaved (never backfilled
# destructively here).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0052_qx15_lead_contact_preference_set_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="code_parrainage",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Code stable partagé par ce client pour parrainer un "
                    "prospect (lien /devis/mon-toit?utm_source=parrainage&"
                    "utm_campaign=<code>)."
                ),
                max_length=20,
                null=True,
                unique=True,
                verbose_name="Code de parrainage",
            ),
        ),
    ]
