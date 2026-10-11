"""AANA51 (D-AANA51 = parquer) — ``PartenaireEdi`` sort de l'ÉTAT Django.

Migration d'ÉTAT seulement (``database_operations=[]``) : AUCUN SQL, la table
``publicapi_partenaireedi`` et sa ligne ``django_migrations`` (0018) sont
conservées — jamais de ``DROP TABLE``. Revertable : ``migrate publicapi 0020``
rend le modèle à l'état ; la restauration du code est dans
``docs/parked-modules.md`` §5.2.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0020_aana32_apievent_payload_encoder'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='PartenaireEdi'),
            ],
            database_operations=[],
        ),
    ]
