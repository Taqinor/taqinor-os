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
from rest_framework.parsers import JSONParser

from apps.calepinage.models import ProfilTypeConsommation
from apps.calepinage.services.profils_types import (
    MENTION_REPLI, SOURCE_REPLI, ProfilEnConflit, ProfilInvalide,
    courbe_journaliere, valider_forme_profils, _profil_de_repli,
    _profils_de_repli,
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
        replis = _profils_de_repli()
        self.assertTrue(replis)
        for profil_repli in replis:
            self.assertEqual(profil_repli['source'], SOURCE_REPLI)
            self.assertEqual(profil_repli['provenance'], MENTION_REPLI)
            self.assertIn('HYPOTHÈSE INTERNE', profil_repli['provenance'])
            self.assertIsNone(profil_repli['id'])

    def test_le_repli_relit_la_constante_du_moteur_de_ventes(self):
        """Jamais une copie : deux copies divergeraient en silence."""
        from apps.ventes.solar_design import TYPICAL_LOAD_PROFILE_RESIDENTIAL

        courbe = _profil_de_repli('residentiel')['courbes']['annuel']
        total = sum(TYPICAL_LOAD_PROFILE_RESIDENTIAL)
        attendue = [valeur / total
                    for valeur in TYPICAL_LOAD_PROFILE_RESIDENTIAL]
        self.assertEqual([round(v, 9) for v in courbe],
                         [round(v, 9) for v in attendue])

    def test_une_cle_inconnue_ne_donne_aucun_repli(self):
        self.assertIsNone(_profil_de_repli('industriel'))


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


class FormeDuPutTest(unittest.TestCase):
    """ERR-ENF11-FUZZ-CALEPINAGE (w4) — la FORME du corps de
    ``PUT parametres/profils-types/`` est jugée avant la base, au chemin
    ``profils[<rang>].<champ>`` que l'écran sait pointer ; la même que le
    schéma publié (``serializers_conso``)."""

    @staticmethod
    def _ligne(**surcharges):
        ligne = {'cle': 'maison-1', 'courbe': {'annuel': JOURNEE},
                 'provenance': 'Relevé de 12 factures, 2025.'}
        ligne.update(surcharges)
        return ligne

    def _refus(self, ligne, champ):
        with self.assertRaises(ProfilInvalide) as capture:
            valider_forme_profils([self._ligne(), ligne])
        self.assertNotIsInstance(capture.exception, ProfilEnConflit)
        self.assertEqual(capture.exception.champ, f'profils[1].{champ}')

    def test_la_forme_conforme_passe_et_la_liste_vide_aussi(self):
        valider_forme_profils([])
        valider_forme_profils([
            self._ligne(),
            self._ligne(cle='Atelier_2', libelle='', famille='industriel',
                        actif=False,
                        courbe={'ete': {'ouvre': JOURNEE, 'weekend': JOURNEE},
                                'hiver': JOURNEE}),
            self._ligne(cle='a' * 60, libelle='x' * 160,
                        courbe={'annuel': [0] * 24})])

    def test_un_corps_qui_n_est_pas_une_liste_d_objets_est_refuse(self):
        for brut in (None, {}, 'x', 5, [None], ['x'], [[]]):
            with self.assertRaises(ProfilInvalide):
                valider_forme_profils(brut)

    def test_cle_libelle_famille_actif_provenance_fautifs(self):
        for cle in (None, '', ' a', 'a b', 'a/b', 'é', 5, 'a' * 61, ['a']):
            self._refus(self._ligne(cle=cle), 'cle')
        for libelle in (None, 5, 'x' * 161, 'a\x00b'):
            self._refus(self._ligne(libelle=libelle), 'libelle')
        for famille in (None, '', 'Residentiel', 'autre ', 0, ['autre'], {}):
            self._refus(self._ligne(famille=famille), 'famille')
        for actif in (None, 0, 1, 'true'):
            self._refus(self._ligne(actif=actif), 'actif')
        for provenance in (None, '', '   ', '\u001c', 'a\x00', 5):
            self._refus(self._ligne(provenance=provenance), 'provenance')

    def test_courbe_fautive(self):
        bonne = JOURNEE
        for courbe in (None, [], {}, 'x', {'annuel': bonne[:23]},
                       {'annuel': bonne + [1.0]}, {'annuel': 'x'},
                       {'annuel': [-1.0] + bonne[1:]},
                       {'annuel': ['1'] * 24}, {'annuel': [True] * 24},
                       {'annuel': [float('nan')] * 24},
                       {'annuel': [float('inf')] * 24},
                       {'mars': bonne}, {'annuel': {}},
                       {'annuel': {'lundi': bonne}},
                       {'annuel': {'ouvre': bonne[:3]}},
                       {'annuel': bonne, 'inconnue': bonne}):
            self._refus(self._ligne(courbe=courbe), 'courbe')

    def test_un_etat_est_un_conflit_pas_une_faute_de_forme(self):
        self.assertTrue(issubclass(ProfilEnConflit, ProfilInvalide))
        # Une journée entièrement nulle et une clé en double (minuscules) sont
        # de FORME conforme : la validation de forme les laisse passer.
        valider_forme_profils([self._ligne(courbe={'annuel': [0.0] * 24}),
                               self._ligne(cle='MAISON-1')])


class PorteDuPutTest(unittest.TestCase):
    """CI #1001 — la porte ``PUT parametres/profils-types/`` juge la FORME avec
    ``valider_forme_profils`` AVANT toute société ou base, et ne prend que du
    JSON (``profils`` est une liste d'objets imbriqués)."""

    @staticmethod
    def _put(corps):
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from apps.calepinage.views.consommation import ProfilsTypesView

        requete = Request(APIRequestFactory().put(
            '/x/', corps, format='json'), parsers=[JSONParser()])
        return ProfilsTypesView().put(requete)

    def test_la_forme_fautive_est_un_400_qui_nomme_la_ligne(self):
        reponse = self._put({'profils': [{'libelle': 'sans clé'}]})
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(list(reponse.data), ['profils[0].cle'])
        reponse = self._put({'profils': 'pas une liste'})
        self.assertEqual((reponse.status_code, list(reponse.data)),
                         (400, ['profils']))

    def test_le_corps_ne_se_donne_qu_en_json(self):
        from apps.calepinage.views.consommation import ProfilsTypesView

        self.assertEqual(ProfilsTypesView.parser_classes, [JSONParser])


class SchemaDuPutTest(unittest.TestCase):
    """Le schéma publié du ``PUT`` porte les bornes du MODÈLE."""

    def test_la_courbe_publiee_suit_le_modele(self):
        from apps.calepinage.serializers_conso import COURBE_PROFIL_SCHEMA

        modele = ProfilTypeConsommation
        self.assertEqual(sorted(COURBE_PROFIL_SCHEMA['properties']),
                         sorted(modele.SAISONS))
        self.assertIs(COURBE_PROFIL_SCHEMA['additionalProperties'], False)
        plat, segmente = COURBE_PROFIL_SCHEMA['properties']['annuel']['oneOf']
        self.assertEqual((plat['minItems'], plat['maxItems']),
                         (modele.HEURES, modele.HEURES))
        self.assertEqual(plat['items'], {'type': 'number', 'minimum': 0})
        self.assertEqual(sorted(segmente['properties']),
                         sorted(modele.JOURS_TYPES))

    def test_les_champs_du_sous_ensemble_ecrit_sont_ceux_du_service(self):
        from apps.calepinage.serializers_conso import (
            ProfilTypeEcritureSerializer,
        )

        champs = ProfilTypeEcritureSerializer().fields
        self.assertEqual(
            champs['cle'].max_length,
            ProfilTypeConsommation._meta.get_field('cle').max_length)
        self.assertEqual(
            champs['libelle'].max_length,
            ProfilTypeConsommation._meta.get_field('libelle').max_length)
        self.assertEqual(sorted(dict(champs['famille'].choices)),
                         sorted(c.value for c in
                                ProfilTypeConsommation.Famille))
        self.assertTrue(champs['courbe'].required)
        self.assertTrue(champs['provenance'].required)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
