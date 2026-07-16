# VX98 — puce de fraîcheur : dernier auteur d'une modification du lead.
# Migration ADDITIVE : un seul champ FK nullable (updated_by), posé server-side
# dans LeadViewSet.perform_update (jamais accepté du corps). NULL sur les leads
# antérieurs à la migration ; date_modification (auto_now) porte l'horodatage.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0055_alter_lead_managers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="updated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leads_modifies",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
