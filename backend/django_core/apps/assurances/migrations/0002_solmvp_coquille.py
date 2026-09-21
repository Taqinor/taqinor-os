"""SOLMVP — coquille de migrations de l'app « assurances ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app assurances`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate assurances 0001_initial`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('assurances', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ActifCouvert'),
                migrations.DeleteModel(name='AttestationAssurance'),
                migrations.DeleteModel(name='EcheancePrime'),
                migrations.DeleteModel(name='ExigenceAssuranceMarche'),
                migrations.DeleteModel(name='GarantiePolice'),
                migrations.DeleteModel(name='IndemnisationSinistre'),
                migrations.DeleteModel(name='DeclarationSinistre'),
                migrations.DeleteModel(name='PoliceAssurance'),
                migrations.DeleteModel(name='Assureur'),
                migrations.DeleteModel(name='Courtier'),
            ],
            database_operations=[],
        ),
    ]
