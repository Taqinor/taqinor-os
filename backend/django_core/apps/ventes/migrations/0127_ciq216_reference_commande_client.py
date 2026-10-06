"""CIQ216 — ``Devis.reference_commande_client`` : numéro de commande du
client (≤ 60), facultatif, vide par défaut.

ADDITIF : une colonne texte à défaut vide, aucun devis existant modifié.
Réversible : ``python manage.py migrate ventes 0126``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0126_ciq214_retenue_penalites'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='reference_commande_client',
            field=models.CharField(
                blank=True, default='', max_length=60,
                verbose_name='Référence de commande du client'),
        ),
    ]
