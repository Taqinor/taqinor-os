"""PV50 — les suggestions du moteur deviennent des ACTIONS applicables.

``recommandations.proposer`` produisait déjà des propositions à gain REJOUÉ
(jamais estimé) et personne ne les publiait : leur ``patch_entree`` est écrit
dans le vocabulaire du MOTEUR (``allee_m``, ``kits``, ``ecarter``…), que
l'écran ne sait pas appliquer. Une suggestion qu'on ne peut pas appliquer d'un
clic n'est pas une suggestion, c'est un conseil — et personne ne suit un
conseil.

Ce module verrouille :

  1. **Les deux familles d'action du contrat partagé** — ``parametres``
     (un patch du dict de paramètres de calepinage) et ``obstacle`` (une
     décision sur un repère nommé) — discriminées par ``action.type``.
  2. **La traduction est EXHAUSTIVE.** Un test lit le vocabulaire de patch que
     ``appliquer_patch`` accepte RÉELLEMENT et exige qu'il soit cartographié :
     le jour où le moteur gagne un levier, ce test rougit au lieu de laisser
     passer une suggestion muette.
  3. **Une clé non cartographiée fait TOMBER la suggestion**, jamais un bouton
     « appliquer » qui n'appliquerait rien.
  4. **Le vocabulaire publié est celui de l'API**, pas celui du moteur :
     ``allee_m`` devient ``allee_min_m``, ``kits`` devient une LISTE de codes
     dans ``kits_autorises``, et ``confirmer`` vise la provenance AO
     ``MESURE`` (que le moteur nomme ``RELEVE``).
  5. **Le plafond de publication** et la fusion multi-surfaces conservatrice.

Run :
    python manage.py test apps.ao.tests.test_pv50_suggestions -v2
"""
import inspect
import json
import re
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.ao import calepinage_io, calepinage_service
from apps.ao.calepinage_serializers import ResultatCalepinageSerializer
from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ObstacleAO, ToitureAO,
    VarianteCalepinage,
)
from authentication.models import Company
from core.calepinage.perf import BudgetCalcul
from core.calepinage.recommandations import appliquer_patch
from core.calepinage.types import Confiance, Recommandation

DOSSIER_CONTRATS = (Path(__file__).resolve().parent.parent
                    / 'contract_samples')

CODE_KIT = 'AO-TABLE-PORTRAIT'

PARAMS = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
    'kits_autorises': [CODE_KIT],
    'pas_recherche_m': 0.01,
}

#: Budget large : ces tests portent sur la TRADUCTION, pas sur la bascule de
#: coût (verrouillée, elle, par ``test_pv49_tiroirs_marges``).
BUDGET_LARGE = BudgetCalcul(seuil_synchrone_ms=1_000_000.0)


def contrat():
    return json.loads(
        (DOSSIER_CONTRATS / 'calepinage_suggestions.json').read_text(
            encoding='utf-8'))


def _recommandation(patch, **surcharges):
    base = {
        'code': 'TEST', 'titre': 'Une proposition', 'gain_modules': 3,
        'gain_kwc': 1.875, 'cout_qualitatif': '', 'confiance': Confiance.HAUTE,
        'patch_entree': patch, 'question_a_poser': 'Peut-on ?',
    }
    base.update(surcharges)
    return Recommandation(**base)


class LaTraductionEstExhaustive(SimpleTestCase):
    """Le jour où le moteur gagne un levier, ce test rougit."""

    @staticmethod
    def _cles_de_patch_du_moteur():
        """Les clés que ``appliquer_patch`` accepte RÉELLEMENT, lues à la source.

        On ne recopie pas une liste à la main : une liste recopiée se périme en
        silence, et c'est précisément la panne qu'on veut rendre impossible.
        """
        source = inspect.getsource(appliquer_patch)
        cles = set(re.findall(r'cle == "([a-z_]+)"', source))
        for groupe in re.findall(r'cle in \(([^)]*)\)', source):
            cles |= set(re.findall(r'"([a-z_]+)"', groupe))
        return cles

    def test_le_vocabulaire_du_moteur_est_entierement_cartographie(self):
        connues = self._cles_de_patch_du_moteur()
        self.assertTrue(connues, 'lecture du vocabulaire de patch en échec')
        cartographiees = (set(calepinage_io.PATCH_MOTEUR_VERS_PARAMS)
                          | set(calepinage_io.PATCH_MOTEUR_VERS_OBSTACLE))
        self.assertEqual(connues, cartographiees)

    def test_les_deux_familles_ne_se_recouvrent_pas(self):
        self.assertFalse(set(calepinage_io.PATCH_MOTEUR_VERS_PARAMS)
                         & set(calepinage_io.PATCH_MOTEUR_VERS_OBSTACLE))


class LeVocabulaireEstTraduit(SimpleTestCase):
    """Le moteur parle sa langue ; l'écran applique la nôtre."""

    def test_une_allee_devient_allee_min_m(self):
        action = calepinage_io.action_de_patch((('allee_m', '1.94'),))
        self.assertEqual(action, {'type': 'parametres',
                                  'patch': {'allee_min_m': 1.94}})

    def test_des_kits_deviennent_une_liste_de_codes_autorises(self):
        action = calepinage_io.action_de_patch((('kits', 'A+B'),))
        self.assertEqual(action, {'type': 'parametres',
                                  'patch': {'kits_autorises': ['A', 'B']}})

    def test_les_rives_gardent_leur_nom_et_deviennent_des_nombres(self):
        action = calepinage_io.action_de_patch(
            (('rive_laterale_m', '0.30'), ('rive_extremite_m', '0.50')))
        self.assertEqual(action['patch'], {'rive_laterale_m': 0.30,
                                           'rive_extremite_m': 0.50})

    def test_l_axe_de_rangee_passe_tel_quel(self):
        action = calepinage_io.action_de_patch((('axe_rangee', 'EST_OUEST'),))
        self.assertEqual(action['patch'], {'axe_rangee': 'EST_OUEST'})

    def test_ecarter_devient_une_action_obstacle(self):
        action = calepinage_io.action_de_patch((('ecarter', 'A'),))
        self.assertEqual(action, {'type': 'obstacle', 'obstacle': 'A',
                                  'provenance': 'ECARTE'})

    def test_confirmer_vise_la_provenance_AO_et_non_celle_du_moteur(self):
        """Le moteur nomme ``RELEVE`` ce que l'AO nomme ``MESURE``."""
        action = calepinage_io.action_de_patch((('confirmer', 'B'),))
        self.assertEqual(action['provenance'], 'MESURE')
        self.assertIn(action['provenance'],
                      dict(ObstacleAO.Provenance.choices))


class UneSuggestionIntraduisibleEstJetee(SimpleTestCase):
    """Mieux vaut ne rien proposer qu'un bouton qui n'applique rien."""

    def test_une_cle_inconnue_fait_tomber_la_suggestion(self):
        self.assertIsNone(
            calepinage_io.action_de_patch((('levier_futur', '1'),)))
        self.assertIsNone(calepinage_io.suggestion_vers_json(
            _recommandation((('levier_futur', '1'),))))

    def test_un_patch_mixte_est_inapplicable_en_un_clic(self):
        self.assertIsNone(calepinage_io.action_de_patch(
            (('allee_m', '1.00'), ('ecarter', 'A'))))

    def test_deux_decisions_d_obstacle_ne_font_pas_une_action(self):
        self.assertIsNone(calepinage_io.action_de_patch(
            (('ecarter', 'A'), ('ecarter', 'B'))))

    def test_un_patch_vide_ne_produit_rien(self):
        self.assertIsNone(calepinage_io.action_de_patch(()))

    def test_les_traduisibles_sont_conservees_les_autres_tombent(self):
        sortie = calepinage_io.suggestions_vers_json([
            _recommandation((('allee_m', '1.00'),), code='BONNE'),
            _recommandation((('levier_futur', '1'),), code='MUETTE'),
        ])
        self.assertEqual([s['code'] for s in sortie], ['BONNE'])


class LaFormeEstCelleDuContratPartage(SimpleTestCase):
    """PACT10 — les clés viennent du fichier versionné, pas d'un mock local."""

    def test_une_suggestion_reste_dans_le_vocabulaire_du_contrat(self):
        autorisees = set()
        actions = set()
        for exemple in contrat()['exemple']['suggestions']:
            autorisees |= set(exemple)
            actions |= set(exemple['action'])
        for patch in ((('allee_m', '1.94'),), (('ecarter', 'A'),)):
            suggestion = calepinage_io.suggestion_vers_json(
                _recommandation(patch))
            self.assertLessEqual(set(suggestion), autorisees)
            self.assertLessEqual(set(suggestion['action']), actions)

    def test_le_gain_est_signe(self):
        """Une perte assumée reste NÉGATIVE : on ne la maquille pas en gain."""
        suggestion = calepinage_io.suggestion_vers_json(
            _recommandation((('ecarter', 'A'),), gain_modules=-4))
        self.assertEqual(suggestion['gain_modules'], -4)


class LaFusionMultiSurfaces(SimpleTestCase):
    """Le moteur propose par SURFACE ; l'écran applique au SITE."""

    @staticmethod
    def _parametres(code, valeur, gain):
        return {'code': code, 'titre': 't', 'gain_modules': gain,
                'gain_kwc': gain * 0.625, 'confiance': 'HAUTE',
                'question_a_poser': '',
                'action': {'type': 'parametres',
                           'patch': {'allee_min_m': valeur}}}

    def test_un_patch_mesure_partout_voit_ses_gains_additionnes(self):
        fusion = calepinage_service._fusionner_suggestions(
            [self._parametres('ALLEE', 1.5, 3),
             self._parametres('ALLEE', 1.5, 4)], 2)
        self.assertEqual(fusion['gain_modules'], 7)
        self.assertAlmostEqual(fusion['gain_kwc'], 4.375, places=3)

    def test_un_patch_mesure_sur_une_seule_surface_est_ecarte(self):
        """L'appliquer partout aurait ailleurs un effet que personne n'a chiffré."""
        self.assertIsNone(calepinage_service._fusionner_suggestions(
            [self._parametres('ALLEE', 1.5, 3)], 2))

    def test_deux_valeurs_differentes_ne_fusionnent_pas(self):
        self.assertIsNone(calepinage_service._fusionner_suggestions(
            [self._parametres('ALLEE', 1.5, 3),
             self._parametres('ALLEE', 2.1, 4)], 2))

    def test_une_decision_d_obstacle_passe_telle_quelle(self):
        obstacle = {'code': 'ARBITRER_A', 'titre': 't', 'gain_modules': 6,
                    'gain_kwc': 3.75, 'confiance': 'MOYENNE',
                    'question_a_poser': '',
                    'action': {'type': 'obstacle', 'obstacle': 'A',
                               'provenance': 'ECARTE'}}
        self.assertEqual(
            calepinage_service._fusionner_suggestions([obstacle], 2), obstacle)


class BasePv50(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV50 Co', slug='pv50-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-50-1', objet='Suggestions')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            contour_local_m=[[0, 0], [30, 0], [30, 18], [0, 18]],
            parametres_calepinage=dict(PARAMS))
        self.kit = KitCalepinage.objects.create(
            company=self.company, code=CODE_KIT,
            libelle='Table dos-à-dos portrait', modules_par_kit=2,
            pas_rangee_m=Decimal('1.134'), longueur_pente_m=Decimal('2.382'),
            faitage_m=Decimal('0.098'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'))
        self.kit.appliquer_emprise()
        self.kit.save()

    def _obstacle(self, repere, x0, provenance=None):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere=repere,
            nature=ObstacleAO.Nature.EDICULE,
            provenance=provenance or ObstacleAO.Provenance.PLAN,
            rect_x0_m=Decimal(str(x0)), rect_x1_m=Decimal(str(x0 + 2)),
            rect_y0_m=Decimal('6.000'), rect_y1_m=Decimal('8.000'))
        obstacle.appliquer_degagement()
        obstacle.save()
        return obstacle

    def _calepiner(self, **kwargs):
        kwargs.setdefault('budget', BUDGET_LARGE)
        return calepinage_service.calepiner(
            calepinage_io.document_entree(self.toiture),
            company=self.company, **kwargs)


class LesDeuxFamillesSortentDuCalcul(BasePv50):
    """Le calcul publie les deux types d'action, sur une vraie toiture."""

    def test_un_obstacle_non_mesure_produit_une_action_obstacle(self):
        self._obstacle('A', 5)
        suggestions = self._calepiner()['suggestions']
        arbitrages = [s for s in suggestions
                      if s['action']['type'] == 'obstacle']
        self.assertTrue(arbitrages, suggestions)
        self.assertEqual(arbitrages[0]['action']['obstacle'], 'A')
        self.assertEqual(arbitrages[0]['action']['provenance'], 'ECARTE')
        self.assertEqual(arbitrages[0]['code'], 'ARBITRER_A')

    def test_une_allee_gratuite_produit_une_action_parametres(self):
        suggestions = self._calepiner()['suggestions']
        patchs = [s for s in suggestions
                  if s['action']['type'] == 'parametres']
        self.assertTrue(patchs, suggestions)
        self.assertIn('allee_min_m', patchs[0]['action']['patch'])

    def test_chaque_suggestion_publiee_porte_une_action_discriminee(self):
        self._obstacle('A', 5)
        for suggestion in self._calepiner()['suggestions']:
            self.assertIn(suggestion['action']['type'],
                          ('parametres', 'obstacle'))

    def test_les_suggestions_sont_capees(self):
        for index, repere in enumerate('ABCDEFG'):
            self._obstacle(repere, 2 + index * 3)
        suggestions = self._calepiner()['suggestions']
        self.assertEqual(calepinage_service.PLAFOND_SUGGESTIONS, 5)
        self.assertLessEqual(len(suggestions),
                             calepinage_service.PLAFOND_SUGGESTIONS)
        # triées par gain DÉCROISSANT : la meilleure d'abord.
        gains = [s['gain_modules'] for s in suggestions]
        self.assertEqual(gains, sorted(gains, reverse=True))

    def test_les_suggestions_peuvent_etre_refusees_a_l_appel(self):
        self._obstacle('A', 5)
        self.assertEqual(self._calepiner(suggestions=False)['suggestions'], [])

    def test_hors_budget_les_suggestions_sont_degradees(self):
        self._obstacle('A', 5)
        sortie = self._calepiner(budget=BudgetCalcul(
            seuil_synchrone_ms=0.0001))
        self.assertEqual(sortie['suggestions'], [])
        self.assertGreater(sortie['total_modules'], 0)

    def test_un_document_multi_surfaces_ne_publie_pas_deux_fois_le_meme_code(
            self):
        document = calepinage_io.document_entree(self.toiture)
        premiere = document['surfaces'][0]
        seconde = dict(premiere, repere=premiere['repere'] + '_B')
        document['surfaces'] = [premiere, seconde]
        document['affectations'] = {premiere['repere']: [],
                                    seconde['repere']: []}
        suggestions = calepinage_service.calepiner(
            document, company=self.company, budget=BUDGET_LARGE
        )['suggestions']
        codes = [s['code'] for s in suggestions]
        self.assertEqual(len(codes), len(set(codes)))

    def test_les_suggestions_ne_sont_pas_persistees(self):
        self._obstacle('A', 5)
        variante = calepinage_service.calculer_variante(self.toiture)
        self.assertNotIn('suggestions', variante.resultat)
        self.assertEqual(
            VarianteCalepinage.objects.filter(company=self.company).count(), 1)


class LeSerialiseurEstLeMiroirDuService(BasePv50):
    """PACT7 — un schéma qui ne dit rien ne contredit rien."""

    def test_les_suggestions_sont_declarees_et_publiees(self):
        self._obstacle('A', 5)
        sortie = self._calepiner()
        self.assertTrue(sortie['suggestions'])
        donnees = ResultatCalepinageSerializer(sortie).data
        self.assertEqual(len(donnees['suggestions']),
                         len(sortie['suggestions']))
        for publiee, attendue in zip(donnees['suggestions'],
                                     sortie['suggestions']):
            self.assertEqual(set(publiee), set(attendue))
            self.assertEqual(set(publiee['action']), set(attendue['action']))
