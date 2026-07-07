# QW10 / YOPSB6 — pose les deux index de dédup (company + phone/email
# normalisé) CONCURREMMENT : crm_lead peut être volumineuse en production, un
# AddIndex nu la verrouillerait en écriture pendant toute la construction.
# Colonnes + backfill vivent dans 0044 ; ici uniquement les index.

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    # CREATE INDEX CONCURRENTLY est interdit dans une transaction.
    atomic = False

    dependencies = [
        ("crm", "0048_xsal17_booking_link"),
    ]

    operations = [
        # Échoue vite (3s) plutôt que de geler la base si un autre verrou long
        # est déjà tenu sur crm_lead.
        migrations.RunSQL(
            sql="SET lock_timeout = '3s';",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="lead",
            index=models.Index(
                fields=["company", "phone_normalise"],
                name="crm_lead_phone_norm_idx",
            ),
        ),
        AddIndexConcurrently(
            model_name="lead",
            index=models.Index(
                fields=["company", "email_normalise"],
                name="crm_lead_email_norm_idx",
            ),
        ),
    ]
