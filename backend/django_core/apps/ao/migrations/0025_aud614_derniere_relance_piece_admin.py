"""AUD614 — marqueur de relance sur les pièces administratives.

Le beat quotidien ``ao.relancer_pieces_administratives`` doit pouvoir dire
« j'ai déjà prévenu récemment ». Sans ce champ, une pièce dans sa fenêtre de
rappel (30 jours par défaut) recevrait une note de chatter CHAQUE MATIN.

ADDITIF et NULLABLE : aucune valeur par défaut à poser sur les lignes
existantes (``NULL`` = jamais relancée, ce qui est vrai), donc aucune écriture
sur la table au déploiement.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0024_affaire_roof_layout'),
    ]

    operations = [
        migrations.AddField(
            model_name='pieceadministrative',
            name='derniere_relance_le',
            field=models.DateField(blank=True, null=True,
                                   verbose_name='Dernière relance'),
        ),
    ]
