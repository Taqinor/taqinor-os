"""CAL150 — couverture = part AUTOCONSOMMÉE, jamais production ÷ consommation.

Ce que ces tests tiennent :

* le test ÉCHOUE si une sortie du module expose un taux calculé comme
  production ÷ consommation (cas construit exprès : production = 2 ×
  consommation, et pourtant couverture < 100 %) ;
* sans courbe horaire, AUCUN taux n'est publié (pas de forfait) ;
* aucun ratio forfaitaire d'autoconsommation n'existe dans le module (test de
  surface sur les sources).

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from apps.calepinage.services.autoconsommation import (
    MOTIF_SANS_COURBE, BilanInvalide, bilan_autoconsommation,
)

RACINE_MODULE = pathlib.Path(__file__).resolve().parent.parent

#: Une journée : consommation à plat, production en cloche diurne.
CONSO_PLATE = [1.0] * 24
PROD_CLOCHE = ([0.0] * 6 + [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
               + [6.0, 5.0, 4.0, 3.0, 2.0, 1.0] + [0.0] * 6)


class CouvAutoTest(unittest.TestCase):

    def test_la_couverture_n_est_PAS_production_sur_consommation(self):
        """Production BIEN SUPÉRIEURE à la consommation, couverture < 100 %."""
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        ratio_interdit = bilan['production_kwh'] / bilan['consommation_kwh']
        # Le cas qui piège : le ratio interdit dépasse 1 (il se lirait
        # « 175 % des besoins couverts »)…
        self.assertGreater(ratio_interdit, 1.0)
        # …alors que la couverture RÉELLE, elle, reste sous 100 %.
        self.assertLess(bilan['taux_couverture'], 1.0)
        self.assertNotEqual(bilan['taux_couverture'], ratio_interdit)

    def test_la_couverture_est_l_autoconsomme_sur_la_consommation(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertAlmostEqual(
            bilan['taux_couverture'],
            round(bilan['autoconsomme_kwh'] / bilan['consommation_kwh'], 4),
            places=4)

    def test_le_taux_d_autoconsommation_est_l_autoconsomme_sur_la_production(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertAlmostEqual(
            bilan['taux_autoconsommation'],
            round(bilan['autoconsomme_kwh'] / bilan['production_kwh'], 4),
            places=4)

    def test_un_champ_geant_ne_couvre_jamais_plus_de_100_pour_cent(self):
        enorme = [valeur * 50 for valeur in PROD_CLOCHE]
        bilan = bilan_autoconsommation(CONSO_PLATE, enorme)
        self.assertLessEqual(bilan['taux_couverture'], 1.0)

    def test_les_totaux_se_referment(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertAlmostEqual(
            bilan['autoconsomme_kwh'] + bilan['import_reseau_kwh'],
            bilan['consommation_kwh'], places=3)
        self.assertAlmostEqual(
            bilan['autoconsomme_kwh'] + bilan['surplus_kwh'],
            bilan['production_kwh'], places=3)

    def test_la_definition_publiee_dit_la_regle(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertIn('COUV-AUTO', bilan['definition'])


class SansCourbeTest(unittest.TestCase):

    def test_sans_courbe_aucun_taux_n_est_publie(self):
        for charge, production in ((None, PROD_CLOCHE),
                                   (CONSO_PLATE, None),
                                   ([], []), (None, None)):
            with self.subTest(charge=bool(charge), prod=bool(production)):
                bilan = bilan_autoconsommation(charge, production)
                self.assertFalse(bilan['publiable'])
                self.assertIsNone(bilan['taux_couverture'])
                self.assertIsNone(bilan['taux_autoconsommation'])
                self.assertEqual(bilan['motif'], MOTIF_SANS_COURBE)

    def test_deux_periodes_differentes_sont_refusees(self):
        with self.assertRaises(BilanInvalide) as refus:
            bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE * 12)
        self.assertIn('même période', str(refus.exception))

    def test_une_heure_illisible_nomme_son_rang(self):
        mauvaise = list(CONSO_PLATE)
        mauvaise[5] = 'beaucoup'
        with self.assertRaises(BilanInvalide) as refus:
            bilan_autoconsommation(mauvaise, PROD_CLOCHE)
        self.assertEqual(refus.exception.champ, 'consommation[5]')


class CibleDeCouvertureTest(unittest.TestCase):
    """ACAL835 — le plus petit N dont la couverture COUV-AUTO atteint la cible.

    Charge plate 1 kW, production 2 kW pour 10 modules : N modules produisent
    0,2 × N kW, donc couvrent 20 % × N (jusqu'à 100 % à 5 modules)."""

    CHARGE = [1.0] * 24
    PRODUCTION = [2.0] * 24

    def _cherche(self, cible, n0=10):
        from apps.calepinage.services.cible_couverture import (
            plus_petit_nombre_pour_couverture)

        return plus_petit_nombre_pour_couverture(
            self.CHARGE, self.PRODUCTION, n0, cible)

    def test_plus_petit_n_a_70_pour_cent(self):
        trouve = self._cherche(70)
        self.assertEqual(trouve['nombre_modules'], 4)  # 3 → 60 %, 4 → 80 %
        self.assertEqual(trouve['couverture_pct'], 80.0)
        self.assertIs(trouve['atteint'], True)
        self.assertEqual(trouve['maximum']['nombre_modules'], 10)

    def test_une_cible_exactement_atteinte_ne_monte_pas_d_un_cran(self):
        self.assertEqual(self._cherche(60)['nombre_modules'], 3)
        self.assertEqual(self._cherche(100)['nombre_modules'], 5)

    def test_cible_inatteignable_dit_le_maximum_sans_depasser_le_pose(self):
        from apps.calepinage.services.cible_couverture import (
            plus_petit_nombre_pour_couverture)

        # Les 3 modules posés produisent 0,6 kW à plat : 60 % au plus.
        trouve = plus_petit_nombre_pour_couverture(
            self.CHARGE, [0.6] * 24, 3, 70)
        self.assertIs(trouve['atteint'], False)
        self.assertIsNone(trouve['nombre_modules'])
        self.assertEqual(trouve['couverture_pct'], 60.0)
        self.assertEqual(trouve['maximum'],
                         {'nombre_modules': 3, 'couverture_pct': 60.0})

    def test_la_couverture_servie_est_celle_du_bilan_horaire(self):
        from apps.calepinage.services.cible_couverture import (
            plus_petit_nombre_pour_couverture)

        # Production en cloche : N0 = 4, la couverture n'est PAS prod ÷ conso.
        trouve = plus_petit_nombre_pour_couverture(
            CONSO_PLATE, PROD_CLOCHE, 4, 30)
        bilan = bilan_autoconsommation(
            CONSO_PLATE, [p * trouve['nombre_modules'] / 4
                          for p in PROD_CLOCHE])
        self.assertEqual(trouve['couverture_pct'],
                         round(100 * bilan['taux_couverture'], 2))
        self.assertGreaterEqual(trouve['couverture_pct'], 30)

    def _serie(self, **colonnes):
        points = [dict({'p_ac_kw': 2.0, 'charge_kwh': 1.0}, **colonnes)
                  for _ in range(24)]
        return {'pas_minutes': 60, 'tronquee': False, 'points': points}

    def test_le_socle_stocke_est_lu_ou_refuse_en_nommant_le_champ(self):
        from apps.calepinage.services.balayage import BalayageInvalide
        from apps.calepinage.services.cible_couverture import lire_socle

        frais = {'simule': True, 'simulation_perimee': False}
        charge, production = lire_socle(frais, self._serie(), 10)
        self.assertEqual((charge[0], production[0], len(charge)), (1.0, 2.0, 24))
        refus = {
            'simulation': [(dict(frais, simule=False), self._serie(), 10),
                           (dict(frais, simulation_perimee=True,
                                 motif='périmée'), self._serie(), 10),
                           (frais, dict(self._serie(), tronquee=True), 10)],
            'pose': [(frais, self._serie(), 0)],
            'electrique.batterie': [(frais, self._serie(
                batterie_soc_pct=50.0), 10)],
            'consommation': [(frais, self._serie(charge_kwh=None), 10)],
            'production': [(frais, self._serie(p_ac_kw=None), 10)],
        }
        for champ, cas in refus.items():
            for servi, serie, n0 in cas:
                with self.assertRaises(BalayageInvalide) as erreur:
                    lire_socle(servi, serie, n0)
                self.assertEqual(erreur.exception.champ, champ)
                self.assertFalse(erreur.exception.forme)

    def test_acal1628_serie_au_jour_dit_le_reglage_et_le_geste(self):
        from apps.calepinage.services.balayage import BalayageInvalide
        from apps.calepinage.services.cible_couverture import lire_socle

        frais = {'simule': True, 'simulation_perimee': False}
        with self.assertRaises(BalayageInvalide) as erreur:
            lire_socle(frais, dict(self._serie(), tronquee=True), 10)
        motif = str(erreur.exception)
        self.assertIn('fenêtre météo', motif)
        self.assertIn('une année', motif)
        self.assertIn('Réglages simulation', motif)
        self.assertIn('dimensionner par objectif', motif)
        self.assertEqual(erreur.exception.champ, 'simulation')

    def test_la_forme_de_l_objectif_est_refusee_en_400(self):
        from apps.calepinage.services.balayage import (
            BalayageInvalide, valider_objectif)

        for objectif in ({'critere': 'autoconsommation', 'cible_pct': 70},
                         {'critere': 'couverture', 'cible_pct': 0},
                         {'critere': 'couverture', 'cible_pct': 100.5},
                         {'critere': 'couverture', 'cible_pct': '70'},
                         {'critere': 'couverture'}, 'couverture'):
            with self.assertRaises(BalayageInvalide) as erreur:
                valider_objectif(None, {'objectif': objectif})
            self.assertTrue(erreur.exception.forme)
            self.assertTrue(erreur.exception.champ.startswith('objectif'))


class SurfaceAucunForfaitTest(unittest.TestCase):
    """Aucun ratio d'autoconsommation forfaitaire dans le module."""

    #: Les noms des ratios forfaitaires de l'écran devis. Ils n'ont RIEN à
    #: faire ici : le module calcule, il ne recopie pas un pourcentage.
    NOMS_INTERDITS = ('AUTOCONSO_SANS', 'AUTOCONSO_AVEC',
                      'TAUX_AUTOCONSO_DEFAUT')

    def test_aucun_ratio_forfaitaire_n_est_employe(self):
        fautifs = []
        for chemin in RACINE_MODULE.rglob('*.py'):
            if 'tests' in chemin.parts or 'migrations' in chemin.parts:
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'),
                              filename=str(chemin))
            identifiants = set()
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Name):
                    identifiants.add(noeud.id)
                elif isinstance(noeud, ast.Attribute):
                    identifiants.add(noeud.attr)
                elif isinstance(noeud, ast.alias):
                    identifiants.add(noeud.name.split('.')[-1])
            for nom in self.NOMS_INTERDITS:
                if nom in identifiants:
                    fautifs.append(f'{chemin.name} : {nom}')
        self.assertEqual(fautifs, [], '; '.join(fautifs))

    def test_le_croisement_vient_du_moteur_unique(self):
        """Une seconde arithmétique d'autoconsommation finirait par diverger."""
        from apps.calepinage.services import autoconsommation

        self.assertIs(
            autoconsommation.hourly_self_consumption.__module__.endswith(
                'solar_design'), True)


class CalepinageDeLeadTest(unittest.TestCase):
    """ACAL2024 (D-ACAL-97) — un calepinage DE LEAD lit autoconsommation et couverture sur la
    conception rangée ; sans lead, il garde son bilan propre."""

    CONCEPTION = {'etat': 'complet', 'marche': 'residentiel', 'option_retenue': 'avec', 'version': 3,
                  'valeurs': {'sans': {'autoconsommation': {'valeur': 0.9}, 'couverture': {'valeur': 0.2}},
                              'avec': {'autoconsommation': {'valeur': 0.42}, 'couverture': {'valeur': 0.61},
                                       'nb_panneaux': {'valeur': 6}}}}

    def _lire(self, calepinage, conception):
        from unittest import mock

        from apps.calepinage.services import devis_retenu
        from apps.calepinage.services.etapes import autoconsommation as etape

        with mock.patch.object(devis_retenu, 'conception_du_calepinage', return_value=conception) as lu:
            return etape.taux_de_la_conception(calepinage), lu

    def test_le_lead_lit_l_option_retenue_de_la_conception(self):
        import types

        taux, lu = self._lire(types.SimpleNamespace(lead_id=7), self.CONCEPTION)
        self.assertEqual(taux, {'taux_autoconsommation': 0.42, 'taux_couverture': 0.61,
                                'version': 3, 'panneaux': 6, 'kwc': None, 'batterie': True})
        lu.assert_called_once()

    def test_sans_lead_ou_sans_conception_complete_rien_n_est_lu(self):
        import types

        taux, lu = self._lire(types.SimpleNamespace(lead_id=None), self.CONCEPTION)
        self.assertIsNone(taux)
        lu.assert_not_called()
        for conception in (None, dict(self.CONCEPTION, etat='refus'), dict(self.CONCEPTION, marche='agricole')):
            self.assertIsNone(self._lire(types.SimpleNamespace(lead_id=7), conception)[0])

    def test_le_bloc_publie_les_taux_de_la_conception_et_le_dit(self):
        from apps.calepinage.services.etapes import autoconsommation as etape
        from apps.calepinage.tests.test_calx190_autoconsommation import contexte_de_test, serie_de_test

        _serie, propre = etape.bloc_autoconsommation(serie_de_test(), contexte_de_test())
        contexte = dict(contexte_de_test(), **{etape.CLE_TAUX_CONCEPTION: {
            'taux_autoconsommation': 0.42, 'taux_couverture': 0.61, 'version': 3, 'panneaux': 6}})
        _serie, lu = etape.bloc_autoconsommation(serie_de_test(), contexte)
        self.assertNotEqual(propre['taux_couverture'], 0.61)
        self.assertEqual((lu['taux_autoconsommation'], lu['taux_couverture']), (0.42, 0.61))
        self.assertIn('conception du lead (version 3, 6 panneaux)', lu['definition'])
        self.assertEqual(lu['energie'], propre['energie'])  # les énergies restent celles de la pose
        self.assertEqual(propre['definition'], etape.DEFINITION_TAUX)
        self.assertEqual((propre['taux_source'], lu['taux_source']), ('pose', 'conception'))

    def _bloc_de_lead(self, conception, kwc_pose=None):
        from apps.calepinage.services.etapes import autoconsommation as etape
        from apps.calepinage.tests.test_calx190_autoconsommation import contexte_de_test, serie_de_test

        contexte = dict(contexte_de_test(), **{etape.CLE_TAUX_CONCEPTION: conception})
        if kwc_pose is not None:
            contexte['plans_poses'] = [{'kwc': kwc_pose - 1.0}, {'kwc': 1.0}]
        return etape.bloc_autoconsommation(serie_de_test(), contexte)[1]

    def test_t4_x7_002_conception_avec_batterie_pose_sans_les_taux_de_la_pose(self):
        """T4-X7-002 — conception « avec batterie » (76 %), pose simulée sans batterie : le bloc ne
        publie pas 76 % à côté d'énergies qui en font 47 % ; il publie les taux de SES énergies."""
        from apps.calepinage.services.etapes import autoconsommation as etape
        from apps.calepinage.tests.test_calx190_autoconsommation import contexte_de_test, serie_de_test

        _serie, propre = etape.bloc_autoconsommation(serie_de_test(), contexte_de_test())
        lu = self._bloc_de_lead({'taux_autoconsommation': 0.42, 'taux_couverture': 0.7654, 'version': 3,
                                 'panneaux': 7, 'kwc': None, 'batterie': True})
        self.assertEqual((lu['taux_autoconsommation'], lu['taux_couverture']),
                         (propre['taux_autoconsommation'], propre['taux_couverture']))
        self.assertNotEqual(lu['taux_couverture'], 0.7654)
        energie = lu['energie']
        self.assertAlmostEqual(lu['taux_couverture'],
                               energie['autoconsomme_kwh'] / energie['consommation_kwh'], places=3)
        self.assertEqual(lu['taux_source'], 'autre_installation')
        self.assertIn('(version 3, 7 panneaux, avec batterie) décrit une autre installation', lu['definition'])

    def test_t4_x7_002_conception_d_une_autre_puissance_les_taux_de_la_pose(self):
        lu = self._bloc_de_lead({'taux_autoconsommation': 0.42, 'taux_couverture': 0.61, 'version': 3,
                                 'panneaux': 7, 'kwc': 3.85, 'batterie': False}, kwc_pose=3.55)
        self.assertNotEqual(lu['taux_couverture'], 0.61)
        self.assertEqual(lu['taux_source'], 'autre_installation')
        self.assertIn('7 panneaux, 3,85 kWc)', lu['definition'])

    def test_t4_x7_002_meme_installation_les_taux_de_la_conception(self):
        """Même puissance, aucune batterie des deux côtés : la règle ACAL2024 tient (taux de la conception)."""
        lu = self._bloc_de_lead({'taux_autoconsommation': 0.42, 'taux_couverture': 0.61, 'version': 3,
                                 'panneaux': 7, 'kwc': 3.55, 'batterie': False}, kwc_pose=3.55)
        self.assertEqual((lu['taux_couverture'], lu['taux_source']), (0.61, 'conception'))
        self.assertIn('conception du lead (version 3, 7 panneaux)', lu['definition'])

    def test_t4_x7_002_aucun_taux_de_conception_pose_et_jamais_autre_installation(self):
        """Revue du 25/11 — sans taux de conception (pas de lead, conception incomplète au moment de
        la simulation, agricole, taux absent : ``CLE_TAUX_CONCEPTION`` vaut ``None``) le bloc garde
        son bilan propre, ``taux_source: 'pose'`` — JAMAIS le signal d'un écart réel."""
        from apps.calepinage.services.etapes import autoconsommation as etape
        from apps.calepinage.tests.test_calx190_autoconsommation import contexte_de_test, serie_de_test

        for contexte in (contexte_de_test(), dict(contexte_de_test(), **{etape.CLE_TAUX_CONCEPTION: None})):
            contexte['plans_poses'] = [{'kwc': 3.55}]
            _serie, bloc = etape.bloc_autoconsommation(serie_de_test(), contexte)
            self.assertEqual(bloc['taux_source'], 'pose')
            self.assertEqual(bloc['definition'], etape.DEFINITION_TAUX)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
