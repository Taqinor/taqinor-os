"""ENF15 — la contrainte d'unicité d'un lead importé (société, système, id externe)
ignore désormais les leads supprimés (soft-delete) : le réimport d'un lead dont
le prédécesseur est supprimé ne heurte plus la contrainte. Plus étroite que
l'ancienne (index partiel conditionnel de plus), donc aucune ligne existante ne
peut la violer. Revertable (RemoveConstraint + AddConstraint inverse).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0136_acrm55_relance_une_ouverte_par_barreau'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='lead',
            name='uniq_lead_external_ref',
        ),
        migrations.AddConstraint(
            model_name='lead',
            constraint=models.UniqueConstraint(condition=models.Q(('external_id__isnull', False), ('is_deleted', False)), fields=('company', 'external_system', 'external_id'), name='uniq_lead_external_ref'),
        ),
    ]
