# QW3 — First-class "call me" vs "WhatsApp only" on the Lead. Additive +
# nullable, distinct from whatsapp_opt_in and Canal.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0042_qw2_lead_site_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="contact_preference",
            field=models.CharField(
                blank=True,
                choices=[
                    ("whatsapp_only", "WhatsApp uniquement"),
                    ("phone_ok", "Rappel téléphonique OK"),
                ],
                max_length=16,
                null=True,
                verbose_name="Préférence de contact",
            ),
        ),
    ]
