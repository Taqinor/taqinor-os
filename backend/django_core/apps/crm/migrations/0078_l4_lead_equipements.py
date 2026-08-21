"""L4 (21/08/2026) — questionnaire d'appel du lead : occupation + équipements.

Huit champs additifs sur ``Lead`` : présence en journée (present/absent/
partiel — pilote la silhouette de consommation servie), piscine / pompe
piscine (kW), véhicule électrique / km parcourus par semaine, climatisation /
nombre de pièces-unités, chauffe-eau électrique. Tous nullable — ``null=True``
veut dire « question pas encore posée », jamais « Non »/un défaut. Distinct de
``futures_charges`` (case web sans paramètre). Voir
``apps/ventes/courbes_journalieres.py`` (fonctions ``_occupation``/
``_equipements``) pour la composition de courbe et la provenance sourcée de
chaque conversion.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0077_wref2_client_ref_provisoire'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='occupation_jour',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('present', 'Présent en journée'),
                         ('absent', 'Absent en journée'),
                         ('partiel', 'Présence partielle (télétravail/mi-temps)')],
                verbose_name='Présence en journée',
                help_text="Question à l'appel : « Y a-t-il quelqu'un à la "
                          'maison en journée ? » (Présent/Absent/Présence '
                          'partielle — vide = pas encore posée). Renseigné : '
                          'PILOTE la silhouette de consommation servie '
                          '(apps/ventes/courbes_journalieres.py _occupation) '
                          '— sinon repli sur le défaut fondateur actuel, '
                          'inchangé.'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_piscine',
            field=models.BooleanField(
                blank=True, null=True, verbose_name='Piscine',
                help_text="Question à l'appel : « Avez-vous une piscine ? » "
                          '(Oui/Non — laisser vide tant que la question '
                          "n'a pas été posée : vide ≠ Non)."),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_piscine_pompe_kw',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Puissance pompe piscine (kW)',
                help_text='Puissance de la pompe de filtration (kW, '
                          'plaque signalétique du moteur). Aucune valeur '
                          'par défaut : le mémo ne cite aucune puissance '
                          'fiable pour ce parc — à relever sur place ou à '
                          'demander au client, sinon laisser vide (aucune '
                          'couche piscine sans cette valeur).'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_voiture_electrique',
            field=models.BooleanField(
                blank=True, null=True, verbose_name='Véhicule électrique',
                help_text="Question à l'appel : « Avez-vous ou "
                          'prévoyez-vous un véhicule électrique ? » '
                          '(Oui/Non — vide = pas encore posée).'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_ve_km_semaine',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='VE — km parcourus/semaine',
                help_text="Question à l'appel : « Combien de km "
                          'parcourez-vous par semaine avec ce véhicule ? » '
                          'SAISIE OBLIGATOIRE pour chiffrer la recharge '
                          '(aucun défaut : mémo étage 2 — conversion '
                          'ADEME 19,8 kWh/100 km, sans hypothèse de '
                          'kilométrage).'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_clim',
            field=models.BooleanField(
                blank=True, null=True, verbose_name='Climatisation',
                help_text="Question à l'appel : « Avez-vous la "
                          'climatisation ? » (Oui/Non — vide = pas '
                          'encore posée).'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_clim_pieces',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                verbose_name='Clim — nombre de pièces/unités',
                help_text="Question à l'appel : « Combien de "
                          'pièces/unités climatisées ? » (chaque unité '
                          '≈ 1,4 kWh/h pour un split 12000 BTU '
                          'non-inverter — mémo étage 2).'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equip_chauffe_eau_electrique',
            field=models.BooleanField(
                blank=True, null=True,
                verbose_name='Chauffe-eau électrique',
                help_text="Question à l'appel : « Votre chauffe-eau "
                          'est-il électrique ? » Champ INFORMATIF '
                          "uniquement : le mémo ne donne qu'un ordre de "
                          'grandeur kWh/personne/an (aucun champ '
                          '« nombre de personnes » collecté) — il '
                          "n'ajuste AUCUNE courbe (omission plutôt "
                          "qu'un défaut inventé)."),
        ),
    ]
