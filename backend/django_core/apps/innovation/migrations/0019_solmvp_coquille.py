"""SOLMVP — coquille de migrations de l'app « innovation ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app innovation`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate innovation 0018_ntide52_email_templates_idee`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0018_ntide52_email_templates_idee'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CampagneInnovation'),
                migrations.DeleteModel(name='FeedbackProduit'),
                migrations.DeleteModel(name='InnovationSettings'),
                migrations.DeleteModel(name='VoteIdee'),
                migrations.DeleteModel(name='AnnonceProduit'),
                migrations.DeleteModel(name='Idee'),
            ],
            database_operations=[],
        ),
    ]
