"""NTDMO27 — toggle global ``Company.tours_actifs`` (défaut True).

Additif : toute société existante garde ``tours_actifs=True`` → comportement
strictement inchangé (les visites guidées NTDMO14/15 restent actives tant
qu'une société ne désactive pas explicitement ce réglage depuis l'onglet
Paramètres « Démo & Onboarding »).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='tours_actifs',
            field=models.BooleanField(
                default=True, verbose_name='Visites guidées actives',
                help_text="Désactive l'apparition automatique de toute visite "
                          "guidée (<ProductTour>, NTDMO14/15) pour les "
                          "nouveaux utilisateurs de cette société. Actif par "
                          "défaut (comportement inchangé)."),
        ),
    ]
