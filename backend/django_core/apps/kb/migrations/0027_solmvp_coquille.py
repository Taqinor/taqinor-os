"""SOLMVP — coquille de migrations de l'app « kb ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app kb`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate kb 0026_ntsrv20_score_utilite`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kb', '0026_ntsrv20_score_utilite'),
        ('migration', '0008_solmvp_coquille'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='BlocReutilisable'),
                migrations.DeleteModel(name='KbArticleAcl'),
                migrations.DeleteModel(name='KbArticleChunk'),
                migrations.DeleteModel(name='KbArticleLien'),
                migrations.DeleteModel(name='KbArticleVersion'),
                migrations.DeleteModel(name='KbFavori'),
                migrations.DeleteModel(name='KbLecture'),
                migrations.DeleteModel(name='KbLectureObligatoire'),
                migrations.DeleteModel(name='KbParcoursArticle'),
                migrations.DeleteModel(name='KbParcoursAssignation'),
                migrations.DeleteModel(name='KbRechercheVide'),
                migrations.DeleteModel(name='PartageArticleKb'),
                migrations.DeleteModel(name='KbArticle'),
                migrations.DeleteModel(name='KbParcours'),
            ],
            database_operations=[],
        ),
    ]
