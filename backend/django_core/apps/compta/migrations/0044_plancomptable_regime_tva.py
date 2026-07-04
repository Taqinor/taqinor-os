"""XACC1 — réglage société ``regime_tva`` sur ``PlanComptable``.

Additif : nouveau champ avec ``default='debit'`` (comportement historique
inchangé pour toute société existante). Aucune donnée à migrer.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0043_dc32_compte_portail_client_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='plancomptable',
            name='regime_tva',
            field=models.CharField(
                choices=[
                    ('debit', 'Débit (fait générateur = facturation)'),
                    ('encaissement',
                     'Encaissement (fait générateur = règlement)'),
                ],
                default='debit',
                max_length=12,
                verbose_name='Régime de TVA',
            ),
        ),
    ]
