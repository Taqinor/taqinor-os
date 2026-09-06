"""AUD233 — réglage société : rapprochement 3 voies automatique (défaut ON).

Additif et revertable : un seul BooleanField sur ``AchatsParametres``. Aucune
donnée existante n'est réécrite — la non-rétroactivité voulue par le fondateur
est portée par le déclencheur (des ÉVÉNEMENTS : confirmation de réception,
évaluation d'une facture liée à un BCF), pas par un rattrapage de l'historique.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0139_aud207_protect_acomptefournisseur_bon_commande'),
    ]

    operations = [
        migrations.AddField(
            model_name='achatsparametres',
            name='rapprochement_3voies_auto',
            field=models.BooleanField(
                default=True,
                help_text="Crée et rafraîchit automatiquement le "
                          "rapprochement 3 voies à la réception et à la "
                          "facturation d'un BCF. Jamais rétroactif sur "
                          "l'historique."),
        ),
    ]
