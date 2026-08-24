"""L-BACK2 (24/08/2026) — créneaux clim/piscine (comble une lacune du L-BACK).

Deux champs additifs sur ``Lead`` : créneau de fonctionnement de la clim,
créneau de filtration de la piscine. Contrairement aux PAIRES chauffe-eau/VE
(kW + créneau ENSEMBLE requis pour produire une couche entièrement neuve),
ces deux créneaux sont des ENRICHISSEMENTS d'une couche DÉJÀ active (clim via
kW déclaré/nombre de pièces, piscine via pompe kW) — même rôle que
``equip_piscine_heures_jour`` : seuls, ils replacent la fenêtre horaire de la
couche existante ; sans cette couche de base, ils ne produisent rien (voir
``apps/ventes/courbes_journalieres.py``).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0079_l_back_lead_equipements_v2'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='equip_clim_creneau',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('matin', 'Matin'), ('apres_midi', 'Après-midi'),
                         ('soir', 'Soir'), ('journee', 'Toute la journée')],
                verbose_name='Créneau de fonctionnement de la clim',
                help_text="Question à l'appel : « À quel moment la "
                          'climatisation tourne-t-elle le plus '
                          '(matin/après-midi/soir/toute la journée) ? » '
                          'Avec la puissance déclarée (ou à défaut '
                          "l'estimation par pièces) : place la couche "
                          '« clim » sur ce créneau au lieu du bloc 13h-21h '
                          'par défaut. Seul, ne change rien.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_piscine_creneau',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('matin', 'Matin'), ('apres_midi', 'Après-midi'),
                         ('soir', 'Soir'), ('journee', 'Toute la journée')],
                verbose_name='Créneau de filtration de la piscine',
                help_text="Question à l'appel : « À quel moment la pompe "
                          'de filtration tourne-t-elle le plus '
                          '(matin/après-midi/soir/toute la journée) ? » '
                          "Change l'heure de DÉPART de la fenêtre "
                          '(equip_piscine_heures_jour en contrôle '
                          'toujours la longueur). Seul, ne change rien.'),
        ),
    ]
