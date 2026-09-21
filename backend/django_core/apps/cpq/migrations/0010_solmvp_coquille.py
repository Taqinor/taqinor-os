"""SOLMVP — coquille de migrations de l'app « cpq ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app cpq`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate cpq 0009_ntcpq30_parametres_tenantmodel`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cpq', '0009_ntcpq30_parametres_tenantmodel'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ClauseCGV'),
                migrations.DeleteModel(name='ContrainteCompatibilite'),
                migrations.DeleteModel(name='EtapeApprobationDevis'),
                migrations.DeleteModel(name='LigneOffreGroupee'),
                migrations.DeleteModel(name='OptionProduit'),
                migrations.DeleteModel(name='ParametresCPQ'),
                migrations.DeleteModel(name='PrixContractuel'),
                migrations.DeleteModel(name='ProduitEquivalent'),
                migrations.DeleteModel(name='RegleProduitCPQ'),
                migrations.DeleteModel(name='ReponseConfigurateur'),
                migrations.DeleteModel(name='SeuilMargeFamille'),
                migrations.DeleteModel(name='OffreGroupee'),
                migrations.DeleteModel(name='QuestionConfigurateur'),
                migrations.DeleteModel(name='RegleApprobationRemise'),
                migrations.DeleteModel(name='SessionConfigurateur'),
            ],
            database_operations=[],
        ),
    ]
