"""CAL153 — cycles, DoD et rendement aller-retour LUS sur la fiche.

Ce qui est tenu :

* chaque grandeur batterie publiée porte ``source: fiche|hypothese`` — une
  hypothèse n'est appliquée QU'EN ÉTANT NOMMÉE, jamais en forfait muet ;
* la limite du port batterie de l'onduleur BORNE la puissance publiée ;
* test avec DEUX packs en parallèle.

La fiche est lue par ``apps.stock.selectors.specs_for_produit`` : on passe ici
des doubles qui portent une ``fiche_technique`` de type ``batterie`` /
``onduleur``, exactement ce que ce sélecteur lit. Aucune base n'est touchée.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.batterie import (
    GRANDEURS_BATTERIE, specs_batterie,
)


class FausseFiche:
    """Le strict nécessaire pour ``specs_for_produit`` : un type + des champs.

    Les attributs absents valent ``None`` (une fiche muette sur un champ),
    ce que le sélecteur traite déjà comme « non renseigné ».
    """

    def __init__(self, type_fiche, **champs):
        self.type_fiche = type_fiche
        self._champs = champs

    def __getattr__(self, nom):
        return self._champs.get(nom)


class FauxProduit:
    def __init__(self, fiche):
        self.fiche_technique = fiche


def batterie(**champs):
    return FauxProduit(FausseFiche('batterie', **champs))


def onduleur(**champs):
    return FauxProduit(FausseFiche('onduleur', **champs))


#: Une fiche batterie COMPLÈTE au sens de CAL118.
FICHE_COMPLETE = dict(bat_kwh_nominal=10.0, bat_kwh_usable=9.0,
                      bat_dod_pct=90.0, bat_rendement_ar_pct=94.0,
                      bat_cycles_publies=6000, bat_max_charge_kw=5.0,
                      bat_max_decharge_kw=5.0)


class SourcesTest(unittest.TestCase):

    def test_chaque_grandeur_publiee_porte_sa_source(self):
        specs = specs_batterie(batterie(**FICHE_COMPLETE))
        for nom in GRANDEURS_BATTERIE:
            with self.subTest(grandeur=nom):
                self.assertIn(specs['grandeurs'][nom]['source'],
                              ('fiche', 'hypothese', None))

    def test_une_fiche_complete_ne_declenche_aucune_hypothese(self):
        specs = specs_batterie(batterie(**FICHE_COMPLETE))
        sources = {nom: specs['grandeurs'][nom]['source']
                   for nom in GRANDEURS_BATTERIE}
        self.assertEqual(sources['dod_pct'], 'fiche')
        self.assertEqual(sources['rendement_ar_pct'], 'fiche')
        self.assertEqual(sources['cycles_publies'], 'fiche')
        self.assertEqual(specs['grandeurs']['cycles_publies']['valeur'],
                         6000.0)
        self.assertEqual(specs['avertissements'], [])

    def test_une_fiche_muette_NOMME_son_hypothese(self):
        sans = dict(FICHE_COMPLETE)
        sans.pop('bat_dod_pct')
        sans.pop('bat_rendement_ar_pct')
        specs = specs_batterie(batterie(**sans))
        for nom in ('dod_pct', 'rendement_ar_pct'):
            with self.subTest(grandeur=nom):
                self.assertEqual(specs['grandeurs'][nom]['source'],
                                 'hypothese')
                self.assertIn('Hypothèse',
                              specs['grandeurs'][nom]['mention'])
        self.assertEqual(len(specs['avertissements']), 2)

    def test_les_cycles_absents_restent_VIDES_sans_hypothese(self):
        """Personne ne peut supposer la durée de vie d'un pack."""
        sans = dict(FICHE_COMPLETE)
        sans.pop('bat_cycles_publies')
        specs = specs_batterie(batterie(**sans))
        self.assertIsNone(specs['grandeurs']['cycles_publies']['valeur'])
        self.assertIsNone(specs['grandeurs']['cycles_publies']['source'])

    def test_sans_produit_aucune_grandeur_n_est_lue_sur_la_fiche(self):
        specs = specs_batterie(None)
        self.assertIsNone(specs['grandeurs']['kwh_usable']['valeur'])
        self.assertIsNone(specs['capacite_utile_kwh'])

    def test_la_capacite_utile_est_deduite_du_dod_si_besoin(self):
        sans = dict(FICHE_COMPLETE)
        sans.pop('bat_kwh_usable')
        specs = specs_batterie(batterie(**sans))
        self.assertEqual(specs['capacite_utile_kwh'], 9.0)
        self.assertTrue(any('UTILE' in avis
                            for avis in specs['avertissements']))


class DeuxPacksTest(unittest.TestCase):
    """« Test avec deux packs en parallèle. »"""

    def test_deux_packs_doublent_la_capacite_et_la_puissance(self):
        un = specs_batterie(batterie(**FICHE_COMPLETE))
        deux = specs_batterie(batterie(**FICHE_COMPLETE), nb_packs=2)
        self.assertEqual(deux['capacite_utile_kwh'],
                         2 * un['capacite_utile_kwh'])
        self.assertEqual(deux['puissance_charge_kw'], 10.0)
        self.assertEqual(deux['nb_packs'], 2)

    def test_le_port_batterie_de_l_onduleur_borne_les_deux_packs(self):
        specs = specs_batterie(
            batterie(**FICHE_COMPLETE), nb_packs=2,
            produit_onduleur=onduleur(ond_bat_max_charge_kw=6.0,
                                      ond_bat_max_decharge_kw=6.0))
        # Deux packs valent 10 kW, mais le port n'en passe que 6.
        self.assertEqual(specs['puissance_charge_kw'], 6.0)
        self.assertEqual(specs['puissance_decharge_kw'], 6.0)
        # …et la capacité, elle, double bien (le port borne la PUISSANCE).
        self.assertEqual(specs['capacite_utile_kwh'], 18.0)
        self.assertTrue(any('BORNÉE' in avis
                            for avis in specs['avertissements']))

    def test_un_port_plus_large_que_le_parc_ne_borne_rien(self):
        specs = specs_batterie(
            batterie(**FICHE_COMPLETE), nb_packs=2,
            produit_onduleur=onduleur(ond_bat_max_charge_kw=20.0,
                                      ond_bat_max_decharge_kw=20.0))
        self.assertEqual(specs['puissance_charge_kw'], 10.0)
        self.assertFalse(any('BORNÉE' in avis
                             for avis in specs['avertissements']))

    def test_un_onduleur_muet_sur_son_port_ne_borne_rien(self):
        specs = specs_batterie(batterie(**FICHE_COMPLETE), nb_packs=2,
                               produit_onduleur=onduleur())
        self.assertEqual(specs['puissance_charge_kw'], 10.0)
        self.assertIsNone(specs['borne_onduleur']['charge_kw'])


class AucunPrixTest(unittest.TestCase):

    def test_aucun_prix_ne_sort_de_ce_service(self):
        specs = specs_batterie(batterie(**FICHE_COMPLETE), nb_packs=2)
        texte = repr(specs)
        for interdit in ('prix', 'achat', 'marge', 'cout'):
            self.assertNotIn(interdit, texte.lower())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
