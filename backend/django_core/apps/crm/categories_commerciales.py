"""Catégories commerciales du lead pro (CIQ401) et talon déclaré par le
client — LA source des choix de ``Lead.categorie_commerciale``.

Décision fondateur 26/10/2026 (lead 1637, boulangerie-pâtisserie classée
« autre ») : la liste couvre les petits et moyens commerces marocains ; les
clés existantes ne bougent pas (aucune valeur perdue). Le moteur C&I tient le
talon par défaut de chaque clé (``apps/ventes/moteur_ci/talons.py``, gardé
identique par ``test_ciq107_profils_charge``).
"""
from django.db import models


class CategorieCommerciale(models.TextChoices):
    HOTEL = 'hotel', 'Hôtel / riad'
    RESTAURANT = 'restaurant', 'Restaurant'
    CAFE = 'cafe', 'Café / salon de thé / glacier'
    BOULANGERIE = 'boulangerie', 'Boulangerie / pâtisserie'
    COMMERCE = 'commerce', 'Commerce / boutique'
    SUPERMARCHE = 'supermarche', 'Supermarché / épicerie (avec frigos)'
    BOUCHERIE = 'boucherie', 'Boucherie / poissonnerie'
    PHARMACIE = 'pharmacie', 'Pharmacie'
    COIFFURE = 'coiffure', 'Coiffure / esthétique'
    PRESSING = 'pressing', 'Pressing / laverie'
    BUREAU = 'bureau', 'Bureaux'
    SANTE = 'sante', 'Santé (clinique, cabinet)'
    ECOLE = 'ecole', 'École'
    SALLE_SPORT = 'salle_sport', 'Salle de sport'
    HAMMAM = 'hammam', 'Hammam / spa'
    GARAGE = 'garage', 'Garage / atelier mécanique'
    ATELIER = 'atelier', 'Atelier (menuiserie, ferronnerie, couture)'
    IMPRIMERIE = 'imprimerie', 'Imprimerie'
    STATION_SERVICE = 'station_service', 'Station-service'
    ENTREPOT = 'entrepot', 'Entrepôt / logistique (sans froid)'
    FROID = 'froid', 'Froid / entrepôt frigorifique'
    MOSQUEE = 'mosquee', 'Mosquée / association'
    AUTRE = 'autre', 'Autre'


#: Clés FERMÉES de ``reponses_categorie`` par catégorie (contrat CIQ1,
#: ``reponses_categorie_par_categorie.cles``) ; une catégorie sans question
#: propre a un tuple vide.
REPONSES_CATEGORIE_CLES = {
    **{cle: () for cle in CategorieCommerciale.values},
    'hotel': ('chambres', 'occupation_pct', 'piscine', 'heures_piscine',
              'blanchisserie', 'reception_24h'),
    'restaurant': ('chambres_froides', 'horaires', 'cuisson',
                   'ouvert_journee_ramadan'),
    'commerce': ('surface_vente_m2', 'chambres_froides'),
    'bureau': ('effectif', 'clim'),
    'sante': ('lits', 'garde_nuit'),
    'ecole': ('effectif', 'internat', 'fermeture_estivale'),
    'hammam': ('surface_m2', 'chauffe'),
    'boulangerie': ('four', 'cuisson_nocturne'),
    'froid': ('temperature_consigne', 'volume_m3', 'saisonnalite_recolte'),
}


class EquipementsHorsHoraires(models.TextChoices):
    """« Avez-vous des équipements qui tournent la nuit ou hors de vos
    horaires (chambres froides, frigos, fours de nuit, pompes) ? »"""
    AUCUN = 'aucun', 'Aucun'
    UN_PEU = 'un_peu', 'Un peu'
    BEAUCOUP = 'beaucoup', 'Beaucoup'


#: Décision fondateur 26/10/2026 — réponse → talon DÉCLARÉ du moteur C&I
#: (``rythme.talon.part_pct`` : part de l'énergie du mois consommée par le
#: talon). Il passe devant le talon par défaut du type de commerce.
TALON_PART_PCT_PAR_REPONSE = {'aucun': 5, 'un_peu': 20, 'beaucoup': 50}
