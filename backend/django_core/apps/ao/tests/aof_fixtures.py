"""Jeu d'essai PARTAGÉ du bordereau FRDISI (Groupe AOF).

Ce module n'est PAS un module de tests (il ne suit pas le motif `test*.py` et
n'est donc pas collecté) : c'est le jeu de données réel du dossier du 27/07,
utilisé par les tests d'AOF123, 125, 127, 128, 129 et 158. Un seul jeu partagé,
pour la même raison que le dossier n'a qu'un seul contexte : si chaque test
retapait les montants, ils divergeraient.

Les chiffres sont ceux du bordereau final, RECALCULÉS ici depuis les quantités
et les prix unitaires :

    A         1 034 100
    B           744 200   (après remontée des câbles DC du bâtiment B)
    C         1 511 300
    communes    877 000
    ------------------------
    total HT  4 166 600
    TVA 20 %    833 320
    total TTC 4 999 920

Le jeu est fourni dans son état AVANT le déplacement demandé par le client (les
câbles DC du bâtiment B sont encore dans les prestations communes), pour que le
test d'AOF123 rejoue le déplacement réel.
"""
from decimal import Decimal

SECTION_A = 'A — Bâtiment A'
SECTION_B = 'B — Bâtiment B'
SECTION_C = 'C — Bâtiment C'
SECTION_COMMUNES = 'Prestations communes'

CLE_CABLES_B = 'cables-dc-b'

#: Sous-totaux ATTENDUS après le déplacement (le bordereau déposé).
SOUS_TOTAUX_ATTENDUS = {
    SECTION_A: Decimal('1034100'),
    SECTION_B: Decimal('744200'),
    SECTION_C: Decimal('1511300'),
    SECTION_COMMUNES: Decimal('877000'),
}

TOTAL_HT = Decimal('4166600')
TVA = Decimal('833320')
TOTAL_TTC = Decimal('4999920')

#: Arrêté officiel du dossier, tel qu'il doit s'imprimer.
ARRETE_TTC = ('QUATRE MILLIONS NEUF CENT QUATRE-VINGT-DIX-NEUF MILLE NEUF '
              'CENT VINGT DIRHAMS')


def _ligne(cle, section, designation, unite, quantite, prix, **extra):
    ligne = {'cle': cle, 'section': section, 'designation': designation,
             'unite': unite, 'quantite': Decimal(str(quantite)),
             'prix_unitaire': Decimal(str(prix)), 'taux_tva': Decimal('20')}
    ligne.update(extra)
    return ligne


def bordereau_avant_deplacement():
    """Le bordereau tel qu'il était AVANT la remarque du client."""
    return [
        # --- Bâtiment A : 448 400 + 234 000 + 4 500 + 8 500 + 338 700
        _ligne('mod-a', SECTION_A, 'Modules photovoltaïques 625 Wc', 'U',
               152, 2950, batiment='A', quantite_source='calepinage'),
        _ligne('ond-a', SECTION_A, 'Onduleurs 110 kW', 'U', 3, 78000,
               batiment='A'),
        _ligne('cof-dc-a', SECTION_A, 'Coffret DC', 'U', 1, 4500,
               batiment='A'),
        _ligne('cof-ac-a', SECTION_A, 'Coffret AC', 'U', 1, 8500,
               batiment='A'),
        _ligne('cab-a', SECTION_A, 'Câblage DC et AC bâtiment A', 'ENS',
               1, 338700, batiment='A'),
        # --- Bâtiment B : 354 000 + 156 000 (les câbles sont ailleurs)
        _ligne('mod-b', SECTION_B, 'Modules photovoltaïques 625 Wc', 'U',
               120, 2950, batiment='B', quantite_source='calepinage'),
        _ligne('ond-b', SECTION_B, 'Onduleurs 110 kW', 'U', 2, 78000,
               batiment='B'),
        # --- Bâtiment C : 849 600 + 390 000 + 15 000 + 256 700
        _ligne('mod-c', SECTION_C, 'Modules photovoltaïques 625 Wc', 'U',
               288, 2950, batiment='C', quantite_source='calepinage'),
        _ligne('ond-c', SECTION_C, 'Onduleurs 110 kW', 'U', 5, 78000,
               batiment='C'),
        _ligne('tgpv-c', SECTION_C, 'TGPV', 'U', 1, 15000, batiment='C'),
        _ligne('cab-c', SECTION_C, 'Câblage DC et AC bâtiment C', 'ENS',
               1, 256700, batiment='C'),
        # --- Prestations communes (877 000 + les 234 200 à déplacer)
        _ligne('meteo', SECTION_COMMUNES, 'Station météorologique', 'U',
               1, 50000),
        _ligne('afficheur', SECTION_COMMUNES, 'Afficheur pédagogique SI22',
               'U', 1, 39500),
        _ligne('etudes', SECTION_COMMUNES, "Études d'exécution", 'ENS',
               1, 262000),
        _ligne('ems', SECTION_COMMUNES, 'Système de management EMS', 'ENS',
               1, 200000),
        _ligne('genie-civil', SECTION_COMMUNES, 'Génie civil', 'ENS',
               1, 120000),
        _ligne('essais', SECTION_COMMUNES, 'Essais, mise en service et DOE',
               'ENS', 1, 70000),
        _ligne('cab-ac-com', SECTION_COMMUNES, 'Câblage AC commun', 'ENS',
               1, 135500),
        _ligne(CLE_CABLES_B, SECTION_COMMUNES, 'Câbles DC Bâtiment B', 'ENS',
               1, 234200, batiment='B'),
    ]


def bordereau_depose():
    """Le bordereau DÉPOSÉ : câbles DC du bâtiment B remontés en section B."""
    from apps.ao.fabrique.ordonnancement import deplacer
    return list(deplacer(bordereau_avant_deplacement(), CLE_CABLES_B,
                         SECTION_B))


def contexte_dossier(lignes=None):
    """Le dossier complet, prêt pour `contexte.construire_contexte`."""
    from apps.ao.fabrique.ordonnancement import totaux
    lignes = list(lignes if lignes is not None else bordereau_depose())
    calcules = totaux(lignes)
    return {
        'identite': {
            'raison_sociale': 'TAQINOR SARL', 'forme_juridique': 'SARL',
            'adresse': '12 rue de l\'Énergie', 'ville': 'Casablanca',
            'ice': '002345678000091', 'rc': '123456', 'if_fiscal': '55667788',
            'cnss': '9988776', 'patente': '30123456',
            'rib': '011 780 0000012345678901 23', 'banque': 'Attijariwafa',
            'signataire': 'Reda Kasri', 'qualite_signataire': 'Gérant',
            'telephone': '+212 6 00 00 00 00', 'email': 'contact@taqinor.ma',
        },
        'acheteur': {'nom': 'FRDISI', 'ville': 'Casablanca',
                     'adresse': 'Route de Nouaceur',
                     'representant': 'Le Directeur'},
        'marche': {
            'objet': "Fourniture, installation et mise en service d'une "
                     'centrale photovoltaïque en toiture',
            'reference_acheteur': 'AO 12/2026', 'reference': 'AO-202608-0001',
            'type_prix': 'unitaires', 'mode_passation': 'appel d\'offres '
                                                        'ouvert',
            'lieu_execution': 'Casablanca', 'delai_execution_jours': 120,
            'validite_offre_jours': 75,
        },
        'batiments': [
            {'code': 'A', 'libelle': 'Aile en L', 'ville': 'Casablanca'},
            {'code': 'B', 'libelle': 'Résidence en arc',
             'ville': 'Casablanca'},
            {'code': 'C', 'libelle': 'École', 'ville': 'Casablanca'},
        ],
        'calepinage': [
            resultat_calepinage('A', 152, 95.0),
            resultat_calepinage('B', 120, 75.0),
            resultat_calepinage('C', 288, 180.0),
        ],
        'equipements': [
            {'role': 'module', 'designation': 'Module 625 Wc',
             'marque': 'JA Solar', 'quantite': 560, 'unite': 'U'},
        ],
        'montants': {
            'sous_total_ht': calcules.sous_total_ht,
            'remise': calcules.remise, 'total_ht': calcules.total_ht,
            'taux_tva': Decimal('20'), 'tva': calcules.tva,
            'total_ttc': calcules.total_ttc, 'devise': 'DH',
        },
        'clauses': {},
        'dates': {'remise_offre': '2026-08-20', 'offre': '2026-08-01'},
        'engagements': [{'batiment': 'A', 'modules': 152},
                        {'batiment': 'B', 'modules': 120},
                        {'batiment': 'C', 'modules': 288}],
    }


def resultat_calepinage(batiment, compte, kwc):
    """Un résultat CONFORME au contrat AOF112."""
    return {'batiment': batiment, 'compte_retenu': compte,
            'compte_optimal': compte, 'optimal': True, 'kwc': kwc,
            'methode': 'dp_exact', 'pas_recherche_m': 0.01,
            'hash_entree': ('%s' % batiment.lower()) * 64,
            'version_moteur': '1.0.0',
            'planche': {'code': 'PL-0%s' % batiment, 'indice': 'A'}}
