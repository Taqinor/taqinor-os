"""YLEDG8 — Relie le PaymentRun compta (FG133) aux factures fournisseurs
stock : ``PaymentRunLine.facture_fournisseur_id`` (référence LÂCHE, jamais
un FK) — additif, aucun champ existant touché.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0074_compensation'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentrunline',
            name='facture_fournisseur_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Facture fournisseur réglée (id stock)'),
        ),
    ]
