"""NTJUR14 — risque éditorial + provision comptable PROPOSÉE.

Trois champs ADDITIFS et nullables sur ``DossierJuridique`` :
``montant_risque_estime`` / ``probabilite_risque`` (appréciation interne, ne
comptabilise RIEN) et ``provision_comptable_id`` (référence LÂCHE vers
``compta.Provision``, posée uniquement par l'action confirmée
``proposer-provision`` — jamais une FK dure vers ``apps.compta``).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('juridique', '0003_ntjur40_approbateur_designe'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossierjuridique',
            name='montant_risque_estime',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                verbose_name='Montant de risque estimé'),
        ),
        migrations.AddField(
            model_name='dossierjuridique',
            name='probabilite_risque',
            field=models.CharField(
                blank=True,
                choices=[('faible', 'Faible'), ('moyenne', 'Moyenne'),
                         ('forte', 'Forte')],
                default='', max_length=10,
                verbose_name='Probabilité du risque'),
        ),
        migrations.AddField(
            model_name='dossierjuridique',
            name='provision_comptable_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='ID de la provision comptable'),
        ),
    ]
