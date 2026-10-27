"""Talon (consommation hors horaires) PAR TYPE DE COMMERCE — décision fondateur
du 26/10/2026 (lead 1637, boulangerie classée « autre »).

Module PUR (aucun import Django). Quand le client déclare ses horaires mais
pas son talon, la courbe SUIT les horaires et le talon (la nuit, les jours
fermés) vaut une part de la puissance des heures ouvertes :

* catégorie avec un archétype SOURCÉ (CIQ107, le sien ou le plus proche) :
  rapport creux / pointe de cet archétype (méthode existante, inchangée) ;
* sinon : ``TALON_DEFAUT_FONDATEUR`` = 20 % — DÉFAUT FONDATEUR, jamais
  présenté comme une donnée sourcée.

Le talon n'est jamais figé : ``rythme.talon`` passe toujours devant — en kW,
en ``part_pct`` (part du mois), ou en ``niveau_jour_pct`` (réponse du
questionnaire « équipements hors horaires », MÊME définition que ces défauts :
un % du niveau des heures ouvertes).

Archétype « le plus proche » : la DÉFINITION officielle des profils BDEW
(G1 bureaux, ateliers, imprimeries ; G2 cafés-restaurants du soir, salles de
sport, stations-service ; G3 commerces à froid important ; G4 boutiques,
coiffeurs) range ce type de commerce dans le profil de l'archétype vendorisé.
"""

#: Défaut fondateur (26/10/2026) : talon = 20 % de la puissance des heures
#: ouvertes, quand aucune source ne donne mieux.
TALON_DEFAUT_FONDATEUR = 0.20
SOURCE_DEFAUT_FONDATEUR = 'défaut fondateur (20 %), décision du 26/10/2026'

#: Définitions des profils BDEW G1-G6 (« Repräsentative VDEW-Lastprofile »,
#: 1999), texte repris par le paquet R flrd/standardlastprofile.
SOURCE_DEFINITIONS_BDEW = (
    'BDEW, définitions des profils G1-G6 (Repräsentative VDEW-Lastprofile, 1999) — '
    'https://github.com/flrd/standardlastprofile/blob/main/data-raw/DATASET.R, '
    'relevé le 2026-10-26')

#: Catégorie → (archétype vendorisé le plus proche, raison tirée de la
#: définition BDEW). Les catégories qui ONT leur archétype n'y sont pas.
ARCHETYPE_LE_PLUS_PROCHE = {
    'cafe': ('restaurant', 'BDEW G2 : « Abendgaststätten » (cafés, restaurants du soir)'),
    'salle_sport': ('restaurant', 'BDEW G2 : « Fitneß- und Sonnenstudios »'),
    'station_service': ('restaurant', 'BDEW G2 : « Tankstellen »'),
    'garage': ('bureau', 'BDEW G1 : « Werkstätten » (ateliers)'),
    'atelier': ('bureau', 'BDEW G1 : « Werkstätten » (ateliers)'),
    'imprimerie': ('bureau', 'BDEW G1 : « Druckereien »'),
    'pharmacie': ('commerce', 'BDEW G4 : « Läden aller Art »'),
    'coiffure': ('commerce', 'BDEW G4 : « Friseurbetriebe »'),
    'pressing': ('commerce', 'BDEW G4 : « Läden aller Art » (horaires de boutique)'),
    'supermarche': ('froid', 'BDEW G3 : « Läden mit erheblichem Bedarf an Kühlung »'),
    'boucherie': ('froid', 'BDEW G3 : « Läden mit erheblichem Bedarf an Kühlung »'),
}

#: Toutes les catégories commerciales du moteur (miroir de
#: ``crm.Lead.CategorieCommerciale``, garde ``test_ciq107_profils_charge``) :
#: ``propre`` = archétype CIQ107 de la catégorie, ``proche`` = archétype le
#: plus proche (ci-dessus), ``defaut`` = talon défaut fondateur seulement.
CATEGORIES_COMMERCE = {
    'hotel': 'propre', 'restaurant': 'propre', 'commerce': 'propre', 'bureau': 'propre',
    'sante': 'propre', 'ecole': 'propre', 'boulangerie': 'propre', 'froid': 'propre',
    **{cle: 'proche' for cle in ARCHETYPE_LE_PLUS_PROCHE},
    'hammam': 'defaut', 'entrepot': 'defaut', 'mosquee': 'defaut', 'autre': 'defaut',
}


def talon_par_defaut(categorie, rapport_archetype=None, source_archetype=None, *,
                     commercial=False):
    """``(rapport talon / puissance ouverte, provenance)`` d'une catégorie
    commerciale, ou ``(None, None)`` hors commerce (industriel, aucune
    catégorie : rien ne dit le talon, la borne conservatrice reste).

    ``rapport_archetype`` : creux / pointe de la forme de l'archétype (propre,
    le plus proche, ou profil SAISI par la société), déjà calculé.
    ``commercial`` : lead commercial SANS catégorie ⇒ défaut fondateur aussi
    (fondateur 27/10/2026) ; l'industriel garde la borne.
    """
    if rapport_archetype:
        return rapport_archetype, {'statut': 'estimation', 'source': source_archetype}
    if categorie == 'industriel' or not (categorie or commercial):
        return None, None
    return TALON_DEFAUT_FONDATEUR, {'statut': 'defaut_fondateur',
                                    'source': SOURCE_DEFAUT_FONDATEUR}
