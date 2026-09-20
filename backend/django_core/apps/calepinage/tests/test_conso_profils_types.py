"""CAL149 — des profils types SAISIS, et des replis ÉTIQUETÉS.

Ce qui est tenu ici (partie PURE, sans base) :

* aucun profil n'est livré sans provenance écrite — le refus est porté par le
  modèle et nomme le champ ;
* les profils codés en dur du dépôt restent en repli mais portent
  ``source='hypothese_interne'`` et la mention qui le dit, PARTOUT où ils
  servent ;
* une courbe est une FORME (des poids normalisés), jamais des kWh supposés ;
* aucune saison n'est extrapolée depuis une autre.
"""
from __future__ import annotations

import unittest

from django.core.exceptions import ValidationError

from apps.calepinage.models import ProfilTypeConsommation
from apps.calepinage.services.profils_types import (
    MENTION_REPLI, SOURCE_REPLI, courbe_journaliere, profil_de_repli,
    profils_de_repli,
)

#: Une journée de test : 24 poids, forme quelconque mais non nulle.
JOURNEE = [1.0] * 6 + [2.0] * 6 + [3.0] * 6 + [4.0] * 6


def profil(**kwargs):
    donnees = {
        'cle': 'residentiel-casa', 'libelle': 'Résidentiel Casablanca',
        'famille': 'residentiel', 'courbe': {'annuel': JOURNEE},
        'provenance': 'Relevé de 12 factures ONEE, client anonymisé, 2025.',
    }
    donnees.update(kwargs)
    return ProfilTypeConsommation(**donnees)


class ProvenanceObligatoireTest(unittest.TestCase):
    """« Aucun profil livré sans provenance écrite. »"""

    def valider(self, objet):
        # ``company`` et ``saisi_par`` sont posés côté serveur : on valide la
        # SAISIE, pas le rattachement.
        objet.full_clean(exclude=['company', 'saisi_par'])

    def test_un_profil_complet_est_accepte(self):
        self.valider(profil())

    def test_sans_provenance_le_profil_est_refuse_en_nommant_le_champ(self):
        for vide in ('', '   '):
            with self.subTest(valeur=repr(vide)):
                with self.assertRaises(ValidationError) as refus:
                    self.valider(profil(provenance=vide))
                self.assertIn('provenance', refus.exception.message_dict)

    def test_une_courbe_vide_est_refusee(self):
        with self.assertRaises(ValidationError) as refus:
            self.valider(profil(courbe={}))
        self.assertIn('courbe', refus.exception.message_dict)

    def test_une_saison_inconnue_est_refusee_en_la_nommant(self):
        with self.assertRaises(ValidationError) as refus:
            self.valider(profil(courbe={'mousson': JOURNEE}))
        self.assertIn('mousson',
                      refus.exception.message_dict['courbe'][0])

    def test_une_courbe_qui_n_a_pas_24_heures_est_refusee(self):
        with self.assertRaises(ValidationError) as refus:
            self.valider(profil(courbe={'hiver': [1.0] * 23}))
        self.assertIn('24', refus.exception.message_dict['courbe'][0])

    def test_une_journee_entierement_nulle_est_refusee(self):
        with self.assertRaises(ValidationError) as refus:
            self.valider(profil(courbe={'ete': [0.0] * 24}))
        self.assertIn('nulle', refus.exception.message_dict['courbe'][0])

    def test_une_heure_negative_est_refusee(self):
        mauvaise = list(JOURNEE)
        mauvaise[3] = -1.0
        with self.assertRaises(ValidationError):
            self.valider(profil(courbe={'annuel': mauvaise}))

    def test_les_quatre_saisons_et_annuel_sont_admis(self):
        for saison in ProfilTypeConsommation.SAISONS:
            with self.subTest(saison=saison):
                self.valider(profil(courbe={saison: JOURNEE}))


class RepliEtiqueteTest(unittest.TestCase):
    """Les profils codés restent — mais ils DISENT qu'ils sont une hypothèse."""

    def test_chaque_repli_porte_sa_source_et_sa_mention(self):
        replis = profils_de_repli()
        self.assertTrue(replis)
        for profil_repli in replis:
            self.assertEqual(profil_repli['source'], SOURCE_REPLI)
            self.assertEqual(profil_repli['provenance'], MENTION_REPLI)
            self.assertIn('HYPOTHÈSE INTERNE', profil_repli['provenance'])
            self.assertIsNone(profil_repli['id'])

    def test_le_repli_relit_la_constante_du_moteur_de_ventes(self):
        """Jamais une copie : deux copies divergeraient en silence."""
        from apps.ventes.solar_design import TYPICAL_LOAD_PROFILE_RESIDENTIAL

        courbe = profil_de_repli('residentiel')['courbes']['annuel']
        total = sum(TYPICAL_LOAD_PROFILE_RESIDENTIAL)
        attendue = [valeur / total
                    for valeur in TYPICAL_LOAD_PROFILE_RESIDENTIAL]
        self.assertEqual([round(v, 9) for v in courbe],
                         [round(v, 9) for v in attendue])

    def test_une_cle_inconnue_ne_donne_aucun_repli(self):
        self.assertIsNone(profil_de_repli('industriel'))


class CourbeJournaliereTest(unittest.TestCase):

    def setUp(self):
        self.profil = {
            'cle': 'essai', 'source': 'societe', 'provenance': 'Comptage.',
            'courbes': {'annuel': [1 / 24.0] * 24,
                        'ete': [0.0] * 12 + [1 / 12.0] * 12},
        }

    def test_sans_energie_la_courbe_est_une_FORME(self):
        courbe, diagnostic = courbe_journaliere(self.profil, saison='annuel')
        self.assertAlmostEqual(sum(courbe), 1.0, places=9)
        self.assertIn('FRACTIONS', diagnostic['motif'])

    def test_avec_energie_la_courbe_est_calee_au_kwh_pres(self):
        courbe, _ = courbe_journaliere(self.profil, saison='ete',
                                       total_kwh=24.0)
        self.assertAlmostEqual(sum(courbe), 24.0, places=9)
        self.assertEqual(courbe[0], 0.0)

    def test_une_saison_absente_retombe_sur_annuel_et_le_dit(self):
        _, diagnostic = courbe_journaliere(self.profil, saison='hiver')
        self.assertEqual(diagnostic['saison_lue'], 'annuel')

    def test_aucune_saison_n_est_extrapolee_depuis_une_autre(self):
        sans_annuel = dict(self.profil,
                           courbes={'ete': self.profil['courbes']['ete']})
        courbe, diagnostic = courbe_journaliere(sans_annuel, saison='hiver')
        self.assertIsNone(courbe)
        self.assertIsNone(diagnostic['saison_lue'])
        self.assertIn('extrapolée', diagnostic['motif'])

    def test_la_provenance_accompagne_toujours_la_courbe(self):
        _, diagnostic = courbe_journaliere(self.profil)
        self.assertEqual(diagnostic['provenance'], 'Comptage.')
        self.assertEqual(diagnostic['source'], 'societe')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
