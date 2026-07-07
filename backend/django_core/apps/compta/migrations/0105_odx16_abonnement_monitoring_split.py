# ODX16 — sortie de ``AbonnementMonitoring`` de compta vers ``apps.monitoring``
# en STATE-ONLY : compta retire le modèle de l'état (SeparateDatabaseAndState,
# zéro SQL) AVANT que monitoring 0004 ne le recrée dans l'état sur la MÊME table
# (db_table='compta_abonnementmonitoring'). Aucune donnée déplacée.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0104_odx9_marketing_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='abonnementmonitoring',
                    name='company',
                ),
                migrations.DeleteModel(
                    name='AbonnementMonitoring',
                ),
            ],
            database_operations=[],
        ),
    ]
