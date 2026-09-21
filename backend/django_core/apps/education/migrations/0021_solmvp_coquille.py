"""SOLMVP — coquille de migrations de l'app « education ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app education`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate education 0020_bulletin_publie_date_publication`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0020_bulletin_publie_date_publication'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AffectationTransport'),
                migrations.DeleteModel(name='Bulletin'),
                migrations.DeleteModel(name='CertificatScolarite'),
                migrations.DeleteModel(name='CompteParent'),
                migrations.DeleteModel(name='CreneauEmploiDuTemps'),
                migrations.DeleteModel(name='IncidentDiscipline'),
                migrations.DeleteModel(name='Inscription'),
                migrations.DeleteModel(name='InscriptionCantine'),
                migrations.DeleteModel(name='LigneEcheance'),
                migrations.DeleteModel(name='MenuCantine'),
                migrations.DeleteModel(name='Note'),
                migrations.DeleteModel(name='ParametresEducation'),
                migrations.DeleteModel(name='Presence'),
                migrations.DeleteModel(name='ArretTransport'),
                migrations.DeleteModel(name='EcheancierScolarite'),
                migrations.DeleteModel(name='Evaluation'),
                migrations.DeleteModel(name='PeriodeScolaire'),
                migrations.DeleteModel(name='Seance'),
                migrations.DeleteModel(name='CircuitTransport'),
                migrations.DeleteModel(name='GrilleTarifaire'),
                migrations.DeleteModel(name='MatiereClasse'),
                migrations.DeleteModel(name='Remise'),
                migrations.DeleteModel(name='Eleve'),
                migrations.DeleteModel(name='Matiere'),
                migrations.DeleteModel(name='Classe'),
                migrations.DeleteModel(name='Famille'),
                migrations.DeleteModel(name='AnneeScolaire'),
                migrations.DeleteModel(name='Niveau'),
            ],
            database_operations=[],
        ),
    ]
