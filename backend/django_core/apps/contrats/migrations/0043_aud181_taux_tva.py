# AUD181 — taux de TVA RÉEL sur Contrat / EcheancierContrat / OrdreLocation.
#
# Sept producteurs de factures figeaient 20 % (``taux_tva=Decimal('20')`` ou
# ``/ Decimal('1.2')`` littéral) sans aucun chemin pour en changer, alors
# qu'un tenant réglant ``CompanyProfile.tva_standard`` à 14 % voyait bien 14 %
# sur ses factures SAV : même grand livre, deux taux.
#
# Les trois champs sont ADDITIFS et NULLABLES — aucune reprise de données,
# aucune contrainte posée sur une table peuplée. NULL veut dire « pas de taux
# propre » : les producteurs replient alors sur le knob société
# (``ventes.utils.company_settings.tva_standard``, défaut 20), donc le
# comportement est byte-identique tant que le knob n'a pas été édité.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0042_wir98_partiecontrat_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='contrat',
            name='taux_tva',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Taux de TVA (%)'),
        ),
        migrations.AddField(
            model_name='echeanciercontrat',
            name='taux_tva',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Taux de TVA (%)'),
        ),
        migrations.AddField(
            model_name='ordrelocation',
            name='taux_tva',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Taux de TVA (%)'),
        ),
    ]
