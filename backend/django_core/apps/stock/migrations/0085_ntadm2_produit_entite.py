"""NTADM2 — champ `entite` OPTIONNEL sur stock.Produit.

Additif pur : colonne nullable, aucun backfill. NULL = « non affecté » —
comportement identique à aujourd'hui pour toutes les lignes existantes.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entites', '0001_initial'),
        ('stock', '0084_apx18_produit_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='entite',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_produits',
                to='entites.entite',
                verbose_name='Entité'),
        ),
    ]
