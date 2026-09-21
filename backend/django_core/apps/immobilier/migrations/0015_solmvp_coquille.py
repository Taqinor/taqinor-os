"""SOLMVP — coquille de migrations de l'app « immobilier ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app immobilier`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate immobilier 0014_photoetatlieux`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('immobilier', '0014_photoetatlieux'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='DepenseCharges'),
                migrations.DeleteModel(name='PhotoEtatLieux'),
                migrations.DeleteModel(name='RegularisationCharges'),
                migrations.DeleteModel(name='RelanceLoyer'),
                migrations.DeleteModel(name='RevisionLoyer'),
                migrations.DeleteModel(name='BudgetCharges'),
                migrations.DeleteModel(name='EcheanceLoyer'),
                migrations.DeleteModel(name='ElementEtatLieux'),
                migrations.DeleteModel(name='PieceEtatLieux'),
                migrations.DeleteModel(name='EtatLieuxImmo'),
                migrations.DeleteModel(name='Bail'),
                migrations.DeleteModel(name='Local'),
                migrations.DeleteModel(name='Locataire'),
                migrations.DeleteModel(name='Niveau'),
                migrations.DeleteModel(name='Batiment'),
                migrations.DeleteModel(name='Site'),
            ],
            database_operations=[],
        ),
    ]
