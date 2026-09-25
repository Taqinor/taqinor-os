"""N1 — report des notifications émises hors de la fenêtre de travail.

Décision fondateur du 25/09/2026 : « les notifications ne doivent pas être à
minuit ni à 23 h — garde toutes les notifications importantes mais place-les
aux heures de travail ». Colonne NULLABLE purement additive (aucune
réécriture de table) : NULL = livrée, toutes les lignes existantes gardent
leur comportement exact. L'index partiel est posé EN CONCURRENT par 0066.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0064_eventtype_dossier_echeance_depassee'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='programmee_pour',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
