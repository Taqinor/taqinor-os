"""SOLMVP — coquille de migrations de l'app « ecommerce_connect ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app ecommerce_connect`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate ecommerce_connect 0002_aud212_connexion_webhook_secret`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce_connect', '0002_aud212_connexion_webhook_secret'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CommandeSync'),
                migrations.DeleteModel(name='ProduitSync'),
                migrations.DeleteModel(name='ConnexionEcommerce'),
            ],
            database_operations=[],
        ),
    ]
