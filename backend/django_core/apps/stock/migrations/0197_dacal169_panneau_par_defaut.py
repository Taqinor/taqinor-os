"""D-ACAL-169 (fondateur, 26/11/2026) — ``Produit.panneau_par_defaut``.

Additive et réversible : un booléen à ``False`` pour tout produit existant (aucun panneau désigné après la migration —
le geste de désigner le 715 W en production reste celui du fondateur), plus deux contraintes :

* ``stock_produit_un_panneau_defaut_par_societe`` — au plus UN produit par société porte le drapeau (unicité
  partielle sur ``company`` quand ``panneau_par_defaut`` est vrai) ;
* ``stock_produit_panneau_defaut_societe`` — un produit GLOBAL (``company`` NULL) ne le porte jamais (NULL est
  distinct pour une unicité PostgreSQL : sans elle, plusieurs produits globaux pourraient le porter).

Toutes deux sont vraies sur les données existantes (drapeau partout à ``False``). Retour arrière = suppression des
deux contraintes puis du champ.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0196_dacal130_prix_structure_sol_pompage'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='panneau_par_defaut',
            field=models.BooleanField(
                default=False,
                help_text='Panneau utilisé par défaut par les choix automatiques (un seul par société).',
                verbose_name='Panneau par défaut'),
        ),
        migrations.AddConstraint(
            model_name='produit',
            constraint=models.UniqueConstraint(
                condition=models.Q(('panneau_par_defaut', True)),
                fields=('company',),
                name='stock_produit_un_panneau_defaut_par_societe'),
        ),
        migrations.AddConstraint(
            model_name='produit',
            constraint=models.CheckConstraint(
                condition=models.Q(('panneau_par_defaut', False), ('company__isnull', False), _connector='OR'),
                name='stock_produit_panneau_defaut_societe'),
        ),
    ]
