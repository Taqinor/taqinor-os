"""CIQ123 — paliers de prix de VENTE par quantité sur ``Produit``.

ADDITIF PUR : une colonne JSON à liste vide (= prix catalogue unique, le
comportement d'hier). Aucun palier n'est semé. RÉVERSIBLE : ``RemoveField``
sans perte (colonne neuve).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0164_ciq103_roles_ci_existants'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='paliers_prix_vente',
            field=models.JSONField(
                blank=True, default=list,
                help_text='Paliers de prix de vente TTC par quantité (vide = '
                          'prix catalogue unique).'),
        ),
    ]
