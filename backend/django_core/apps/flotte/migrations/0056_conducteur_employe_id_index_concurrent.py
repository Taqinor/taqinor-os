# YOPSB6 — pose l'index composite (company, employe_id) sur flotte_conducteur
# CONCURREMMENT pour ne pas verrouiller la table en écriture. La colonne
# employe_id est ajoutée dans 0055 ; ici uniquement l'index.

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    # CREATE INDEX CONCURRENTLY est interdit dans une transaction.
    atomic = False

    dependencies = [
        ("flotte", "0055_conducteur_employe_id_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SET lock_timeout = '3s';",
            reverse_sql=migrations.RunSQL.noop,
        ),
        AddIndexConcurrently(
            model_name="conducteur",
            index=models.Index(
                fields=["company", "employe_id"],
                name="flotte_cond_co_emp_idx",
            ),
        ),
    ]
