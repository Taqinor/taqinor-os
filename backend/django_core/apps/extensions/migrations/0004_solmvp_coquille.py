"""SOLMVP — coquille de migrations de l'app « extensions ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app extensions`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate extensions 0003_ntext14_extensioninstall`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('extensions', '0003_ntext14_extensioninstall'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ExtensionInstall'),
                migrations.DeleteModel(name='ExtensionPackage'),
            ],
            database_operations=[],
        ),
    ]
