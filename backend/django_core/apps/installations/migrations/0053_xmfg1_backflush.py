import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0052_dc34_soustraitant_fournisseur'),
        ('stock', '0026_fg67_frais_annexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordreassemblage',
            name='emplacement_source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_assemblage_source', to='stock.emplacementstock'),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='emplacement_destination',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_assemblage_destination', to='stock.emplacementstock'),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='quantite_produite',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='stock_mouvemente',
            field=models.BooleanField(default=False),
        ),
    ]
