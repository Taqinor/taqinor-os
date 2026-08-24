"""L-BACK (24/08/2026) — grandeurs complémentaires du bloc équipements L4.

Six champs additifs sur ``Lead``, tous nullable, EN PAIRES : puissance
chauffe-eau (kW) + créneau, puissance chargeur VE (kW) + créneau, puissance
clim déclarée (kW), heures de filtration piscine/jour. Une seule moitié d'une
paire renseignée ne produit aucune couche de consommation (même règle
« zéro chiffre inventé » que le bloc L4 — voir
``apps/ventes/courbes_journalieres.py``).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0078_l4_lead_equipements'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='equip_chauffe_eau_kw',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Puissance chauffe-eau (kW)',
                help_text='Puissance de la résistance du chauffe-eau '
                          'électrique (kW, plaque signalétique). Avec le '
                          'créneau ci-dessous : compose une couche '
                          '« impulsion » sur ce créneau. Seule, ne produit '
                          'rien.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_chauffe_eau_creneau',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('matin', 'Matin'), ('soir', 'Soir'),
                         ('nuit', 'Nuit'),
                         ('journee', 'Toute la journée')],
                verbose_name='Créneau de chauffe du chauffe-eau',
                help_text="Question à l'appel : « À quel moment le "
                          'chauffe-eau chauffe-t-il le plus '
                          '(matin/soir/nuit/toute la journée) ? » Avec la '
                          'puissance ci-dessus : compose une couche '
                          '« impulsion » sur ce créneau. Seul, ne produit '
                          'rien.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_ve_chargeur_kw',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Puissance chargeur VE (kW)',
                help_text='Puissance du chargeur du véhicule électrique '
                          '(kW, prise renforcée/wallbox). Avec le créneau '
                          "ci-dessous : borne la fenêtre de recharge à "
                          "l'énergie hebdomadaire ÷ cette puissance, au "
                          'lieu de la fenêtre 21h-6h par défaut. Seule, ne '
                          'change rien.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_ve_creneau',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('nuit', 'Nuit'), ('jour', 'Jour'),
                         ('soir', 'Soir')],
                verbose_name='Créneau de recharge du VE',
                help_text="Question à l'appel : « À quel moment "
                          'rechargez-vous le véhicule (nuit/jour/soir) ? » '
                          'Avec la puissance ci-dessus : borne la fenêtre '
                          'de recharge réelle. Seul, ne change rien.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_clim_kw',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Puissance clim déclarée (kW)',
                help_text='Puissance totale RÉELLE de la climatisation '
                          '(kW, relevée sur plaque signalétique), quand '
                          "elle est connue : remplace l'estimation par "
                          'défaut (pièces × 1,4 kWh/h non-inverter). '
                          'Vide : la couche clim reste composée depuis '
                          'le nombre de pièces.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_piscine_heures_jour',
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=4, null=True,
                verbose_name='Piscine — heures de filtration/jour',
                help_text='Durée réelle de filtration déclarée (h/jour), '
                          'quand elle est connue : remplace la durée par '
                          'défaut du mémo (8h, bloc 10h-18h). Vide : la '
                          'couche piscine reste composée avec la fenêtre '
                          'par défaut.'),
        ),
    ]
