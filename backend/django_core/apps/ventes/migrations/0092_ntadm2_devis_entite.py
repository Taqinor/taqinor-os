"""NTADM2 — champ `entite` OPTIONNEL sur ventes.Devis.

Additif pur : colonne nullable, aucun backfill. NULL = « non affecté » —
comportement identique à aujourd'hui pour toutes les lignes existantes.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entites', '0001_initial'),
        ('ventes', '0091_protect_produit_donnees_reelles'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='entite',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ventes_devis',
                to='entites.entite',
                verbose_name='Entité'),
        ),
    ]
