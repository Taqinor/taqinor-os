# ACAL320 (C-ACAL-065) — retrait de ParametresCalepinage.gabarits_dossier,
# jumelle DORMANTE du modèle GabaritDossierReglementaire (le seul mécanisme
# réel, lu par services/reglementaire.py) : aucune lecture hors sérialisation.
#
# DRY-RUN AVANT DÉPLOIEMENT (lecture seule, accès prod en lecture) :
#   ParametresCalepinage.objects.exclude(gabarits_dossier={}).count()
# — la liste des sociétés concernées est soumise au fondateur.
# Réversible : RemoveField se rejoue à l'envers (colonne recréée, défaut {}).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0030_acal297_responsable_stocke'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='parametrescalepinage',
            name='gabarits_dossier',
        ),
    ]
