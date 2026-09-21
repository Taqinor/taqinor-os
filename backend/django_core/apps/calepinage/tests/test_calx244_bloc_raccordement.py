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

#: Les cinq contrôles, dans l'ordre où le contrat les publie.
CODES = ['elevation_tension', 'puissance_souscrite', 'regime_phases',
         'tension_nominale', 'desequilibre_phases']

#: Les quatre grandeurs du bloc ``calcul``.
CHAMPS_CALCUL = {'elevation_pct', 'ecart_limite_pct', 'puissance_injectee_kva',
                 'desequilibre_pct'}

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

        self.assertEqual(sorted(bloc), ['calcul', 'saisie', 'verdicts'],
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
