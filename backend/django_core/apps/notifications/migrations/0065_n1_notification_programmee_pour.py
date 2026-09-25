"""N1 — report des notifications émises hors de la fenêtre de travail.

Décision fondateur du 25/09/2026 : « les notifications ne doivent pas être à
minuit ni à 23 h — garde toutes les notifications importantes mais place-les
aux heures de travail ». Colonne NULLABLE purement additive : NULL = livrée
(toutes les lignes existantes gardent leur comportement exact). Index
PARTIEL : seules les lignes en attente de livraison y entrent.
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
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(
                condition=models.Q(('programmee_pour__isnull', False)),
                fields=['programmee_pour'],
                name='notif_programmee_pour_idx'),
        ),
    ]
