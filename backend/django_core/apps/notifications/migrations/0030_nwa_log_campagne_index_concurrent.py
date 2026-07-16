# XMKT10 / YOPSB6 — pose l'index composite (company, campagne_id) du log
# WhatsApp CONCURREMMENT : la table de logs peut être volumineuse en
# production, un AddIndex nu la verrouillerait en écriture. La colonne vit
# dans 0026 ; ici uniquement l'index.

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    # CREATE INDEX CONCURRENTLY est interdit dans une transaction.
    atomic = False

    dependencies = [
        ("notifications", "0029_alter_notification_event_type_and_more"),
    ]

    operations = [
        # Échoue vite (3s) plutôt que de geler la base si un autre verrou long
        # est déjà tenu sur la table cible.
        migrations.RunSQL(
            sql="SET lock_timeout = '3s';",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="whatsappmessagelog",
            index=models.Index(
                fields=["company", "campagne_id"],
                name="nwa_log_company_campagne_idx",
            ),
        ),
    ]
