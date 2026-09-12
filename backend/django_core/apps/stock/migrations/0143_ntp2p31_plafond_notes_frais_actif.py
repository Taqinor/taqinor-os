"""NTP2P31 — Réglages Procure-to-Pay par société : troisième interrupteur.

Additif pur : ``AchatsParametres.plafond_notes_frais_actif`` à ``False``.
Ne pilote QUE la notification immédiate du valideur direction (NTP2P45) —
le calcul d'escalade NTP2P11 lui-même reste inchangé (actif dès qu'un
``PlafondNoteFrais`` est configuré, indépendamment de ce réglage).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0142_ntp2p9_tolerance_categorie'),
    ]

    operations = [
        migrations.AddField(
            model_name='achatsparametres',
            name='plafond_notes_frais_actif',
            field=models.BooleanField(default=False),
        ),
    ]
