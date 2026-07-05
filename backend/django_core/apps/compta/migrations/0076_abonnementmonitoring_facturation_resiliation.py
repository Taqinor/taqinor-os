"""YSUBS3/YSUBS4 — AbonnementMonitoring : dernière période facturée (garde
d'idempotence de facturation récurrente) + motif de résiliation — additif,
aucun champ existant touché.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0075_paymentrunline_facture_fournisseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='abonnementmonitoring',
            name='derniere_facturation',
            field=models.DateField(blank=True, null=True, verbose_name='Dernière période facturée'),
        ),
        migrations.AddField(
            model_name='abonnementmonitoring',
            name='motif_resiliation',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Motif de résiliation'),
        ),
    ]
