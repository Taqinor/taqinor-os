"""Décision fondateur 26/10/2026 (lead 1637) — catégories commerciales
complétées pour les petits et moyens commerces marocains (clés existantes
inchangées : aucune valeur perdue ; max_length 12 → 20 pour
``station_service``) et réponse « équipements hors horaires » (talon déclaré
du moteur C&I). ADDITIVE et réversible : un AlterField de choix + une colonne
nullable.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0141_equipecommerciale_recoit_leads'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='categorie_commerciale',
            field=models.CharField(blank=True, choices=[('hotel', 'Hôtel / riad'), ('restaurant', 'Restaurant'), ('cafe', 'Café / salon de thé / glacier'), ('boulangerie', 'Boulangerie / pâtisserie'), ('commerce', 'Commerce / boutique'), ('supermarche', 'Supermarché / épicerie (avec frigos)'), ('boucherie', 'Boucherie / poissonnerie'), ('pharmacie', 'Pharmacie'), ('coiffure', 'Coiffure / esthétique'), ('pressing', 'Pressing / laverie'), ('bureau', 'Bureaux'), ('sante', 'Santé (clinique, cabinet)'), ('ecole', 'École'), ('salle_sport', 'Salle de sport'), ('hammam', 'Hammam / spa'), ('garage', 'Garage / atelier mécanique'), ('atelier', 'Atelier (menuiserie, ferronnerie, couture)'), ('imprimerie', 'Imprimerie'), ('station_service', 'Station-service'), ('entrepot', 'Entrepôt / logistique (sans froid)'), ('froid', 'Froid / entrepôt frigorifique'), ('mosquee', 'Mosquée / association'), ('autre', 'Autre')], help_text="Question à l'appel : « Quelle est votre activité : hôtel, restaurant ou café, commerce, bureaux, santé, école, hammam, boulangerie, froid, ou autre chose ? » (vide = pas encore posée).", max_length=20, null=True, verbose_name='Activité (catégorie commerciale)'),
        ),
        migrations.AddField(
            model_name='lead',
            name='equipements_hors_horaires',
            field=models.CharField(blank=True, choices=[('aucun', 'Aucun'), ('un_peu', 'Un peu'), ('beaucoup', 'Beaucoup')], help_text="Question à l'appel : « Avez-vous des équipements qui tournent la nuit ou hors de vos horaires (chambres froides, frigos, fours de nuit, pompes) ? » — talon déclaré du moteur C&I (vide = pas encore posée).", max_length=8, null=True, verbose_name='Équipements hors horaires'),
        ),
    ]
