"""VISITE-CADENCE — ``VisiteTerrain.qualification`` (JSON, NULL).

Ordre fondateur du 15/09/2026 : le commercial terrain qualifie le client avant
de repartir (température, sort du devis, décideur, frein, déclencheur, moment
de rappel), et cette lecture remonte dans l'historique du lead.

Purement ADDITIF et sans risque de déploiement : colonne NULLABLE, sans valeur
par défaut, sur une table existante — aucune réécriture de ligne, aucun verrou
long, et les visites déjà en base restent à ``NULL`` (ce qui est la vérité :
personne ne les a qualifiées).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('visites', '0003_vta6_progression_terrain'),
    ]

    operations = [
        migrations.AddField(
            model_name='visiteterrain',
            name='qualification',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name='Qualification de fin de visite'),
        ),
    ]
