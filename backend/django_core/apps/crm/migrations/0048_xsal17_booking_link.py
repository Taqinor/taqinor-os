# XSAL17 — BookingLink: tokenized, expiring per-lead visit-booking link
# resolved by the {lien_rdv} message-template placeholder. Additive new
# model, no changes to existing tables.

import django.db.models.deletion
import apps.crm.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0047_xsal9_client_parent"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingLink",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("token", models.CharField(
                    default=apps.crm.models._default_booking_token,
                    editable=False, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(
                    default=apps.crm.models._default_booking_expiry)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("appointment", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="booking_link_origine",
                    to="crm.appointment")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="booking_links", to="authentication.company")),
                ("lead", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="booking_links", to="crm.lead")),
            ],
            options={
                "verbose_name": "Lien de réservation RDV",
                "verbose_name_plural": "Liens de réservation RDV",
                "ordering": ["-created_at"],
            },
        ),
    ]
