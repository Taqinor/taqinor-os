"""AACQ16 — Type de budget d'un ad set miroir (quotidien / à vie).

Purement ADDITIVE : une colonne ``budget_type`` (défaut vide = inconnu) ;
aucune donnée existante touchée — entièrement revertable.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0057_veille_decouverte'),
    ]

    operations = [
        migrations.AddField(
            model_name='adsetmirror',
            name='budget_type',
            field=models.CharField(
                blank=True, default='', max_length=16,
                verbose_name='Type de budget (quotidien / à vie)'),
        ),
    ]
