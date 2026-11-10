# ACON28 — le statut DÉRIVÉ « Refusé » rejoint les choix (AlterField seul).
#
# Aucune donnée réécrite : le statut d'un calepinage est DÉRIVÉ de son
# approbation (services.approbation.statut_derive), jamais stocké.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0033_acon6_variante_devis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='calepinage',
            name='statut',
            field=models.CharField(
                choices=[('brouillon', 'Brouillon'), ('valide', 'Validé'),
                         ('perime', 'Périmé'), ('refuse', 'Refusé')],
                db_index=True, default='brouillon', max_length=12,
                verbose_name='Statut'),
        ),
    ]
