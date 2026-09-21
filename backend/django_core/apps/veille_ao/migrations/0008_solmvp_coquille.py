"""SOLMVP — coquille de migrations de l'app « veille_ao ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app veille_ao`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate veille_ao 0007_vao29_acheteur_cible`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('veille_ao', '0007_vao29_acheteur_cible'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AcheteurCible'),
                migrations.DeleteModel(name='AvisMarche'),
                migrations.DeleteModel(name='ExecutionCollecte'),
                migrations.DeleteModel(name='MotCleVeille'),
                migrations.DeleteModel(name='RegleExclusion'),
                migrations.DeleteModel(name='SourceVeille'),
            ],
            database_operations=[],
        ),
    ]
