"""CIQ216 — ``Facture.reference_commande_client`` : numéro de commande du
client hérité du devis (facture de BC, facture de tranche).

ADDITIF : une colonne texte à défaut vide, aucune facture existante modifiée.
Réversible : ``python manage.py migrate facturation 0011``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0011_ciq215_ventilation_tva'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='reference_commande_client',
            field=models.CharField(
                blank=True, default='', max_length=60,
                verbose_name='Référence de commande du client'),
        ),
    ]
