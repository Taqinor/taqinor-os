"""AUD713 — un seul dépôt BDS PRINCIPAL par période (contrainte DB).

Le modèle ``DepotBDS`` PROMETTAIT dans sa docstring qu'« une période ne peut
avoir qu'UN dépôt principal » sans qu'aucune contrainte ne le garantisse.
Contrainte PARTIELLE (conditionnée à ``type_depot='principal'``) : les dépôts
COMPLÉMENTAIRES restent librement multiples, comme avant. Réversible
(``RemoveConstraint``).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0044_aud703_archive_pdf_bulletin'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='depotbds',
            constraint=models.UniqueConstraint(
                condition=models.Q(type_depot='principal'),
                fields=('company', 'periode'),
                name='uniq_depot_bds_principal_par_periode',
            ),
        ),
    ]
