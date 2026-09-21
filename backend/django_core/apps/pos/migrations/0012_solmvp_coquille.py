"""SOLMVP — coquille de migrations de l'app « pos ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app pos`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate pos 0011_aud205_quantite_positive`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0011_aud205_quantite_positive'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CodePinCaissier'),
                migrations.DeleteModel(name='ConfigMaterielPOS'),
                migrations.DeleteModel(name='LigneCommandeRetrait'),
                migrations.DeleteModel(name='LigneVenteComptoir'),
                migrations.DeleteModel(name='PrixParEmplacement'),
                migrations.DeleteModel(name='ShareLinkTicket'),
                migrations.DeleteModel(name='CommandeRetrait'),
                migrations.DeleteModel(name='VenteComptoir'),
                migrations.DeleteModel(name='SessionCaisse'),
            ],
            database_operations=[],
        ),
    ]
