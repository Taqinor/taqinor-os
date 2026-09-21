"""SOLMVP — coquille de migrations de l'app « ai_governance ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app ai_governance`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate ai_governance 0007_ntai7_aifeaturetoggle`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai_governance', '0007_ntai7_aifeaturetoggle'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AiFeatureToggle'),
                migrations.DeleteModel(name='DriftSnapshot'),
                migrations.DeleteModel(name='ExtractionCorrection'),
                migrations.DeleteModel(name='LlmBudget'),
                migrations.DeleteModel(name='LlmUsageRecord'),
                migrations.DeleteModel(name='PromptTemplateVersion'),
                migrations.DeleteModel(name='DocumentAiJob'),
                migrations.DeleteModel(name='PromptTemplate'),
            ],
            database_operations=[],
        ),
    ]
