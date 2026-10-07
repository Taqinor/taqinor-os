"""ASTK44 — coût unitaire porté par les entrées de production.

ADDITIF PUR : une colonne décimale NULLABLE sur ``MouvementStock``. Les
mouvements existants restent à NULL (comportement inchangé : le coût moyen ne
les lit pas comme couche). RÉVERSIBLE : ``RemoveField`` sans perte (colonne
neuve).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0165_ciq123_paliers_vente'),
    ]

    operations = [
        migrations.AddField(
            model_name='mouvementstock',
            name='cout_unitaire',
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=14, null=True),
        ),
    ]
