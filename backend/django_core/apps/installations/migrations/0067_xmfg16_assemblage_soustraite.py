import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0066_xfsm5_fenetre_rdv'),
        ('stock', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordreassemblage',
            name='sous_traitant',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='installations_ordres_assemblage_soustraites',
                to='stock.fournisseur'),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='ordre_sous_traitance',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ordres_assemblage',
                to='installations.ordresoustraitance'),
        ),
    ]
