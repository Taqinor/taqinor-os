"""CALX244 — le document du raccordement, et la route qui le sert.

CE QUE CE FICHIER PROUVE, SANS BASE DE DONNÉES
-----------------------------------------------
1. ``services/raccordement.py::bloc_raccordement`` rend EXACTEMENT les trois
   blocs du contrat CALX205 (``contract_samples/calepinage_raccordement
   .json``), avec les CINQ verdicts dans l'ordre publié — et, quand rien
   n'est saisi, l'état ``exemple_vide`` mot pour mot : c'est la promesse
   qu'un écran n'a jamais à tester l'absence d'une clé.
2. Une saisie ILLISIBLE est refusée en NOMMANT son champ
   (``raccordement.<champ>``) : l'écran pose le message SOUS le champ fautif
   (règle fondateur du 08/09/2026), jamais un « non enregistré » générique.
3. Un verdict ``non_verifiable`` du noyau (CALX215) est publié ``omis`` avec
   son MOTIF — jamais un chiffre, jamais une pastille verte.
4. La route ``calepinages/<pk>/raccordement/`` existe, sert GET **et** POST,
   et son action est découverte par le routeur DRF (greffe par affectation :
   le piège CALX7 est qu'un nom d'attribut différent du ``__name__`` fait
   disparaître la route en silence).

AUCUN SEUIL n'est écrit ici : les seules valeurs comparées sont celles de
l'échantillon et celles du cas de test, et la règle vérifiée est un LIEN
entre champs, jamais un nombre opposable.

Run :
    python manage.py test apps.calepinage.tests.test_calx244_bloc_raccordement
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase
from django.urls import reverse

from apps.calepinage.services.raccordement import (
    CHAMPS_SAISIE, RaccordementInvalide, bloc_raccordement,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
RACCORDEMENT = json.loads(
    (ECHANTILLONS / 'calepinage_raccordement.json').read_text(
        encoding='utf-8'))

# ACAL155 (plafond d'injection) et ACAL157 (proposition du lead) servent
# les clés posées par ACAL9 (M0) : l'échantillon est comparé TEL QUEL.

#: Les cinq contrôles, dans l'ordre où le contrat les publie.
CODES = ['elevation_tension', 'puissance_souscrite', 'regime_phases',
         'tension_nominale', 'desequilibre_phases']

#: Les six grandeurs du bloc ``calcul`` (ACAL827 : + plafond A converti).
CHAMPS_CALCUL = {'elevation_pct', 'ecart_limite_pct', 'puissance_injectee_kva',
                 'desequilibre_pct', 'plafond_injection_kw_converti',
                 'plafond_injection_conversion'}

#: Les cinq champs d'un verdict publié.
CHAMPS_VERDICT = {'code', 'libelle', 'statut', 'detail', 'source'}

#: Un tronçon ALTERNATIF complet — longueur, section et courant d'emploi tels
#: que ``services/troncons.py`` les publie. Les valeurs sont celles du cas de
#: test : aucune ne vient d'un texte ni d'un barème.
TRONCON_AC = {
    'id': 'AC1', 'cote': 'ac', 'de': 'ONDU1', 'vers': 'TGBT',
    'longueur_m': 30.0, 'longueur_origine': 'plan — cheminement tracé',
    'section_mm2': 10.0, 'ib_a': 16.0,
}

#: Le même tronçon côté CONTINU : il est en amont de l'onduleur, donc il ne
#: participe pas à l'élévation au point de livraison.
TRONCON_DC = dict(TRONCON_AC, id='DC1', cote='dc')

#: Une saisie complète et SOURCÉE (valeurs du cas de test).
SAISIE = {
    'puissance_souscrite_kva': 12.0,
    'phases': 3,
    'tension_nominale_v': 400.0,
    'limite_elevation_pct': 3.0,
    'source_limite': "contrat de raccordement d'essai",
    'cos_phi_impose': 0.9,
    'source_cos_phi': "contrat de raccordement d'essai",
}


def _par_code(bloc):
    return {verdict['code']: verdict for verdict in bloc['verdicts']}


class FormeDuDocumentTest(SimpleTestCase):
    """Les trois blocs, les sept saisies, les cinq verdicts — toujours."""

    def test_les_trois_blocs_et_rien_d_autre(self):
        bloc = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})

        # ACAL157 — la proposition du lead est la quatrième clé racine.
        # ACAL782 — + ``regime`` ; ACAL783 — + ``injection`` et son motif.
        self.assertEqual(sorted(bloc), ['calcul', 'injection',
                                        'injection_motif', 'proposition_lead',
                                        'regime', 'saisie', 'verdicts'],
                         "Le contrat CALX205 publie TROIS blocs : une clé "
                         "racine de plus, et l'écran lit un document que "
                         "l'échantillon committé ne décrit pas.")

    def test_les_sept_champs_de_saisie_sont_republies(self):
        bloc = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})

        self.assertEqual(sorted(bloc['saisie']), sorted(CHAMPS_SAISIE))
        self.assertEqual(sorted(bloc['saisie']),
                         sorted(RACCORDEMENT['exemple']['saisie']))

    def test_les_quatre_grandeurs_calculees(self):
        bloc = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})

        self.assertEqual(set(bloc['calcul']), CHAMPS_CALCUL)

    def test_plafond_en_ampere_converti_en_kw(self):
        """ACAL827 — 16 A, 3 phases, 400 V, cos φ 1 ⇒ 11,085 kW et sa
        formule ; champ manquant ⇒ null nommé ; kW + A ⇒ refus."""
        saisie = dict(SAISIE, tension_nominale_v=400.0, cos_phi_impose=1.0,
                      plafond_injection_a=16.0,
                      plafond_injection_justification="contrat d'essai")
        bloc = bloc_raccordement(None, saisie, [TRONCON_AC], {})
        self.assertEqual(bloc['saisie']['plafond_injection_a'], 16.0)
        self.assertEqual(bloc['calcul']['plafond_injection_kw_converti'],
                         11.085)
        self.assertEqual(bloc['calcul']['plafond_injection_conversion'],
                         '3 phases : √3 × 400 V × 16 A × cos φ 1 = '
                         '11,085 kW')
        mono = bloc_raccordement(
            None, dict(saisie, phases=1, tension_nominale_v=230.0),
            [TRONCON_AC], {})
        self.assertEqual(mono['calcul']['plafond_injection_kw_converti'],
                         3.68)
        self.assertTrue(mono['calcul']['plafond_injection_conversion']
                        .startswith('Monophasé : 230 V'))
        sans_cos = bloc_raccordement(
            None, dict(saisie, cos_phi_impose=None, source_cos_phi=None),
            [TRONCON_AC], {})
        self.assertIsNone(sans_cos['calcul']['plafond_injection_kw_converti'])
        self.assertIn('cos φ imposé',
                      sans_cos['calcul']['plafond_injection_conversion'])
        aucun = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})
        self.assertIsNone(aucun['calcul']['plafond_injection_kw_converti'])
        self.assertIsNone(aucun['calcul']['plafond_injection_conversion'])
        with self.assertRaises(RaccordementInvalide) as refus:
            bloc_raccordement(None, dict(saisie, plafond_injection_kw=5.0),
                              [TRONCON_AC], {})
        self.assertEqual(refus.exception.champ,
                         'raccordement.plafond_injection_a')
        with self.assertRaises(RaccordementInvalide) as negatif:
            bloc_raccordement(None, dict(saisie, plafond_injection_a=-1),
                              [TRONCON_AC], {})
        self.assertEqual(negatif.exception.champ,
                         'raccordement.plafond_injection_a')
        with self.assertRaises(RaccordementInvalide) as sans_just:
            bloc_raccordement(
                None, dict(saisie, plafond_injection_justification=None),
                [TRONCON_AC], {})
        self.assertTrue(sans_just.exception.etat)

    def test_simulation_recoit_le_kw_converti(self):
        from apps.calepinage.services.limites_livraison import (
            saisie_pour_simulation)

        lu = saisie_pour_simulation(dict(
            SAISIE, cos_phi_impose=1.0, plafond_injection_a=16.0,
            plafond_injection_kw=None))
        self.assertEqual(lu['plafond_injection_kw'], 11.085)
        self.assertNotIn('plafond_injection_a', lu)

    def test_les_cinq_verdicts_dans_l_ordre_du_contrat(self):
        bloc = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})

        self.assertEqual([verdict['code'] for verdict in bloc['verdicts']],
                         CODES,
                         "Un écran qui reçoit parfois cinq verdicts et "
                         "parfois deux finit par tester l'absence de clé.")
        for verdict in bloc['verdicts']:
            with self.subTest(code=verdict['code']):
                self.assertEqual(set(verdict), CHAMPS_VERDICT)

    def test_chaque_libelle_est_celui_du_contrat(self):
        bloc = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})
        attendus = {verdict['code']: verdict['libelle']
                    for verdict in RACCORDEMENT['exemple']['verdicts']}

        for verdict in bloc['verdicts']:
            with self.subTest(code=verdict['code']):
                self.assertEqual(verdict['libelle'],
                                 attendus[verdict['code']])


class EtatVideTest(SimpleTestCase):
    """Rien de saisi, rien de tracé : l'état ``exemple_vide``, mot pour mot."""

    def _vide(self):
        return bloc_raccordement(None, {}, [], {})

    def test_le_document_vide_est_celui_du_contrat(self):
        self.assertEqual(
            self._vide(), RACCORDEMENT['exemple_vide'],
            "L'état vide servi diverge de l'échantillon committé : c'est "
            "exactement ce que le contrat CALX205 existe pour empêcher.")

    def test_aucune_grandeur_n_est_publiee_a_zero(self):
        for champ, valeur in self._vide()['calcul'].items():
            with self.subTest(champ=champ):
                self.assertIsNone(valeur,
                                  "`0` se lirait « mesuré et nul », alors "
                                  "que rien n'a été calculé.")

    def test_les_cinq_verdicts_sont_omis_et_disent_pourquoi(self):
        for verdict in self._vide()['verdicts']:
            with self.subTest(code=verdict['code']):
                self.assertEqual(verdict['statut'], 'omis')
                self.assertTrue(verdict['detail'].strip())
                self.assertIsNone(verdict['source'])


class RegimeDuSiteTest(SimpleTestCase):
    """ACAL782 — le régime 82-21 est publié avec sa base, sans seuil local."""

    def _regime(self, dc=None, ac=None, hors_reseau=False):
        return bloc_raccordement(
            None, {}, [], {}, puissance_dc_kwc=dc, puissance_ac_kw=ac,
            hors_reseau=hors_reseau)['regime']

    def test_douze_kwc_publie_l_accord_de_raccordement(self):
        regime = self._regime(12, 10)

        self.assertEqual(regime['code'], 'accord_raccordement')
        self.assertEqual(regime['libelle'], 'Accord de raccordement')
        self.assertEqual(regime['puissance_retenue_kw'], 12)
        self.assertEqual(regime['base_puissance'],
                         'a_confirmer_avec_le_distributeur')
        self.assertEqual(regime['guichet_statut'], 'a_confirmer')
        self.assertTrue(regime['base'].strip())
        self.assertFalse(regime['a_qualifier'])

    def test_la_puissance_retenue_est_le_max_de_dc_et_ac(self):
        self.assertEqual(self._regime(8, 12)['puissance_retenue_kw'], 12)

    def test_hors_reseau_publie_la_declaration_hors_reseau(self):
        regime = self._regime(12, 10, hors_reseau=True)

        self.assertEqual(regime['libelle'], 'Déclaration hors réseau')

    def test_sans_puissance_le_regime_est_a_qualifier(self):
        regime = self._regime()

        self.assertTrue(regime['a_qualifier'])
        self.assertIsNone(regime['code'])


class InjectionFaceAuPlafondTest(SimpleTestCase):
    """ACAL783 — la part injectée simulée face au plafond légal (lu, jamais
    recopié) ; un avertissement, jamais un blocage."""

    #: Plafond tel que le selector de ``ventes`` le sert (valeur de cas).
    PLAFOND = {'pct': 20, 'source': 'source du cas',
               'mention_bt': 'mention BT du cas'}

    def _injection(self, surplus, production=10000.0, plafond=PLAFOND):
        autoconso = {'energie': {'surplus_kwh': surplus,
                                 'production_kwh': production}}
        return bloc_raccordement(None, {}, [], {}, autoconsommation=autoconso,
                                 plafond_legal=plafond)

    def test_trente_cinq_pour_cent_depasse_et_avertit(self):
        bloc = self._injection(3500.0)

        injection = bloc['injection']
        self.assertEqual(injection['part_injectee_pct'], 35.0)
        self.assertEqual(injection['plafond_pct'], 20)
        self.assertTrue(injection['depasse'])
        self.assertEqual(injection['mention'], 'mention BT du cas')
        self.assertIn('(35 %)', injection['avertissement'])
        self.assertIn('20 %', injection['avertissement'])
        self.assertIsNone(bloc['injection_motif'])
        self.assertEqual([v['statut'] for v in bloc['verdicts']],
                         [v['statut'] for v in
                          self._injection(1500.0)['verdicts']],
                         "Un avertissement ne change aucun verdict.")

    def test_quinze_pour_cent_ne_depasse_pas(self):
        injection = self._injection(1500.0)['injection']

        self.assertFalse(injection['depasse'])
        self.assertIsNone(injection['avertissement'])

    def test_exactement_le_plafond_ne_depasse_pas(self):
        self.assertFalse(self._injection(2000.0)['injection']['depasse'])

    def test_sans_simulation_injection_nulle_et_motif(self):
        bloc = bloc_raccordement(None, {}, [], {})

        self.assertIsNone(bloc['injection'])
        self.assertEqual(bloc['injection_motif'],
                         "Simulez d'abord pour comparer l'injection")

    def test_le_selector_ventes_sert_la_constante(self):
        from apps.ventes.quote_engine import constants_82_21 as c
        from apps.ventes.selectors_calepinage import (
            plafond_injection_loi_8221,
        )

        plafond = plafond_injection_loi_8221()

        self.assertEqual(plafond['pct'], c.PLAFOND_INJECTION_PCT)
        self.assertEqual(plafond['mention_bt'], c.MENTION_BT)


class OmissionsNommeesTest(SimpleTestCase):
    """Ce qui manque est NOMMÉ — jamais remplacé par un chiffre."""

    def test_sans_limite_l_elevation_est_publiee_et_le_verdict_omis(self):
        sans_limite = dict(SAISIE, limite_elevation_pct=None,
                           source_limite=None)

        bloc = bloc_raccordement(None, sans_limite, [TRONCON_AC], {})

        self.assertIsNotNone(bloc['calcul']['elevation_pct'],
                             "L'élévation est un chiffre VRAI : elle se "
                             "publie même sans limite à lui opposer.")
        self.assertIsNone(bloc['calcul']['ecart_limite_pct'],
                          "`ecart_limite_pct` est une DIFFÉRENCE : sans limite, il "
                          "n'y a rien à soustraire.")
        verdict = _par_code(bloc)['elevation_tension']
        self.assertEqual(verdict['statut'], 'omis')
        self.assertIn('limite_elevation_pct', verdict['detail'])

    def test_un_troncon_sans_courant_omet_l_elevation(self):
        ampute = dict(TRONCON_AC)
        ampute.pop('ib_a')

        bloc = bloc_raccordement(None, SAISIE, [ampute], {})

        self.assertIsNone(bloc['calcul']['elevation_pct'],
                          "Une somme partielle sous-estimerait l'élévation "
                          "tout en ayant l'air d'un résultat.")

    def test_seul_le_cote_alternatif_est_parcouru(self):
        avec_dc = bloc_raccordement(None, SAISIE,
                                    [TRONCON_DC, TRONCON_AC], {})
        ac_seul = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})

        self.assertEqual(avec_dc['calcul']['elevation_pct'],
                         ac_seul['calcul']['elevation_pct'],
                         "Un tronçon continu est en amont de l'onduleur : "
                         "il ne remonte pas la tension du point de "
                         "livraison.")

    def test_sans_cheminement_aucune_elevation_n_est_supposee(self):
        bloc = bloc_raccordement(None, SAISIE, [], {})

        self.assertIsNone(bloc['calcul']['elevation_pct'])
        self.assertEqual(_par_code(bloc)['elevation_tension']['statut'],
                         'omis')

    def test_sans_seuil_societe_le_desequilibre_reste_sans_verdict(self):
        bloc = bloc_raccordement(None, SAISIE, [TRONCON_AC], {})
        verdict = _par_code(bloc)['desequilibre_phases']

        self.assertEqual(verdict['statut'], 'omis')
        self.assertIn('seuil_desequilibre_pct', verdict['detail'])


class RefusNommentLeChampTest(SimpleTestCase):
    """Un refus désigne le champ : l'écran sait sous lequel poser l'erreur."""

    def _refus(self, **ecarts):
        with self.assertRaises(RaccordementInvalide) as capture:
            bloc_raccordement(None, dict(SAISIE, **ecarts), [TRONCON_AC], {})
        return capture.exception

    def test_limite_sans_source(self):
        refus = self._refus(source_limite=None)

        self.assertEqual(refus.champ, 'raccordement.source_limite')
        self.assertEqual(
            str(refus),
            RACCORDEMENT['refus_limite_sans_source']['source_limite'])

    def test_cos_phi_sans_source(self):
        refus = self._refus(source_cos_phi='   ')

        self.assertEqual(refus.champ, 'raccordement.source_cos_phi')
        self.assertEqual(
            str(refus),
            RACCORDEMENT['refus_cos_phi_sans_source']['source_cos_phi'])

    def test_phases_hors_1_et_3(self):
        refus = self._refus(phases=2)

        self.assertEqual(refus.champ, 'raccordement.phases')
        self.assertIn('1', str(refus))
        self.assertIn('3', str(refus))

    def test_une_puissance_illisible_est_refusee_pas_avalee(self):
        refus = self._refus(puissance_souscrite_kva='douze')

        self.assertEqual(refus.champ,
                         'raccordement.puissance_souscrite_kva')

    def test_une_tension_nulle_n_est_pas_une_tension(self):
        refus = self._refus(tension_nominale_v=0)

        self.assertEqual(refus.champ, 'raccordement.tension_nominale_v')

    def test_une_valeur_demesuree_est_refusee_pas_calculee(self):
        # ERR-ENF11-FUZZ-CALEPINAGE : 1e308 faisait deborder les calculs (500).
        for champ in ('puissance_souscrite_kva', 'tension_nominale_v',
                      'limite_elevation_pct', 'cos_phi_impose',
                      'plafond_injection_kw'):
            refus = self._refus(**{champ: 1.1e308})
            self.assertEqual(refus.champ, 'raccordement.' + champ)

    def test_une_cle_inconnue_est_ignoree_pas_enregistree(self):
        bloc = bloc_raccordement(None, dict(SAISIE, numero_compteur='X1'),
                                 [TRONCON_AC], {})

        self.assertNotIn('numero_compteur', bloc['saisie'])


class RouteServieTest(SimpleTestCase):
    """La route existe, elle sert les DEUX méthodes, et DRF la découvre."""

    def test_le_chemin_est_celui_du_contrat(self):
        _verbe, _, route = RACCORDEMENT['endpoint'].partition(' ')

        self.assertEqual(reverse('calepinage-raccordement', args=('1',)),
                         route.replace('<int:pk>', '1'))

    def test_l_action_est_decouverte_par_le_routeur(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet

        noms = {action.__name__
                for action in CalepinageViewSet.get_extra_actions()}

        self.assertIn(
            'raccordement', noms,
            "L'action greffée par affectation n'est plus découverte : DRF "
            "inspecte la classe AU MOMENT de router.register, et il mappe "
            "par __name__ (piège CALX7).")

    def test_les_deux_methodes_sont_servies(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet

        par_nom = {action.__name__: action
                   for action in CalepinageViewSet.get_extra_actions()}

        self.assertEqual(set(par_nom['raccordement'].mapping),
                         {'get', 'post'},
                         "Le POST rend le raccordement recalculé : sans lui, "
                         "l'appelant devrait enchaîner un second appel.")

    def test_le_module_est_declare_dans_la_liste_append_only(self):
        from apps.calepinage.views import rattachements

        self.assertIn('raccordement', rattachements.MODULES_RATTACHES)
