"""NTWMS5 — traçabilité CASIER sur MouvementStock (poste scanner).

Additif et réversible : deux colonnes NULLABLES vers la hiérarchie de casiers
FG319 (``installations.BinLocation``, jamais dupliquée dans stock). Tous les
mouvements existants restent à NULL — comportement strictement inchangé.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0034_binlocation_binaffectation_and_more'),
        ('stock', '0087_ntwms4_vague_picking'),
    ]

    operations = [
        migrations.AddField(
            model_name='mouvementstock',
            name='bin_source',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mouvements_stock_source',
                to='installations.binlocation'),
        ),
        migrations.AddField(
            model_name='mouvementstock',
            name='bin_destination',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mouvements_stock_destination',
                to='installations.binlocation'),
        ),
    ]
