"""SOLMVP — coquille de migrations de l'app « paie ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app paie`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate paie 0054_ntpay24_gabarit_declaratif`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0054_ntpay24_gabarit_declaratif'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AdhesionMutuelle'),
                migrations.DeleteModel(name='AvanceSalarie'),
                migrations.DeleteModel(name='CumulAnnuel'),
                migrations.DeleteModel(name='DepotBDS'),
                migrations.DeleteModel(name='DepotDeclaratif'),
                migrations.DeleteModel(name='ElementVariable'),
                migrations.DeleteModel(name='GabaritDeclaratif'),
                migrations.DeleteModel(name='LigneBulletin'),
                migrations.DeleteModel(name='LigneVirement'),
                migrations.DeleteModel(name='ParametragePaieCompany'),
                migrations.DeleteModel(name='ParametrePaie'),
                migrations.DeleteModel(name='ProvisionPaieMensuelle'),
                migrations.DeleteModel(name='RubriqueEmploye'),
                migrations.DeleteModel(name='SaisieArret'),
                migrations.DeleteModel(name='SchemaComptablePaie'),
                migrations.DeleteModel(name='StructurePaieRubrique'),
                migrations.DeleteModel(name='TrancheIR'),
                migrations.DeleteModel(name='VentilationAnalytiquePaie'),
                migrations.DeleteModel(name='BaremeIR'),
                migrations.DeleteModel(name='BulletinPaie'),
                migrations.DeleteModel(name='EcheanceDeclarative'),
                migrations.DeleteModel(name='OrdreVirement'),
                migrations.DeleteModel(name='RegimeMutuelle'),
                migrations.DeleteModel(name='Rubrique'),
                migrations.DeleteModel(name='TypeEntreePonctuelle'),
                migrations.DeleteModel(name='PeriodePaie'),
                migrations.DeleteModel(name='ProfilPaie'),
                migrations.DeleteModel(name='PaysPaie'),
                migrations.DeleteModel(name='StructurePaie'),
            ],
            database_operations=[],
        ),
    ]
