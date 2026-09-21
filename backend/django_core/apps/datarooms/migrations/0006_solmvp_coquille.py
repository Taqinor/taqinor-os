"""SOLMVP — coquille de migrations de l'app « datarooms ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app datarooms`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate datarooms 0005_ntdoc16_fermeture`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datarooms', '0005_ntdoc16_fermeture'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AccesSalleDonnees'),
                migrations.DeleteModel(name='SalleDeDonneesDocument'),
                migrations.DeleteModel(name='SalleDeDonnees'),
            ],
            database_operations=[],
        ),
    ]
