"""CAL78 — ``POST /calepinage/moteur/pose/`` : la POSE et son régime de preuve.

Ce qui est prouvé ici :

* la route EXISTE et sert le chemin que le contrat committé fige depuis le
  jour 1 (``contract_samples/pose.json``) — l'appel du client frontend
  (``calepinageApi.moteur.pose``) ne pointe plus dans le vide ;
* la réponse porte EXACTEMENT les clés du contrat, ni plus ni moins : c'est
  la garde qui empêche les deux moitiés d'inventer deux vocabulaires
  (PACT10, incident AO du 03/08/2026) ;
* le relevé voyage sous ``demande`` ;
* elle ne REFAIT aucune sérialisation : elle appelle la MÊME porte neutre du
  moteur que ``calculer`` (``moteur_service.calepinage_json``), et ne
  demande pas de suggestions — on ne paye pas ce qu'on ne publie pas
  (ACAL292 : les tiroirs AO n'existent plus) ;
* le ``verdict`` est GÉNÉRÉ des grandeurs mesurées, jamais rédigé ;
* un corps absent rend 400 ; un relevé bien formé que le moteur refuse rend
  409 en NOMMANT le champ fautif, jamais un 500 ;
* la route est gardée par ``calepinage_gerer``, pas par ``ao_gerer``.

Le MOTEUR lui-même n'est pas retesté ici (il a ses tests dans
``core/calepinage`` et ``apps/ao``) : ce fichier prouve la PORTE.

Run :
    python manage.py test apps.calepinage.tests.test_api_pose -v2
"""
import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.views.moteur import MoteurPoseView, verdict_de_pose

from .test_api_liste import BaseApiCalepinage

URL = '/api/django/calepinage/moteur/pose/'

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'pose.json').read_text(encoding='utf-8'))

#: La sortie du moteur — SUR-ENSEMBLE de ce que la pose publie (c'est la
#: sérialisation commune du dépôt : ``calculer`` en publie plus).
SORTIE_MOTEUR = dict(
    CONTRAT['exemple'],
    company_id=1, depuis_cache=False, engagement_modules=None,
    rangees=[], suggestions=[])
SORTIE_MOTEUR.pop('verdict')
SORTIE_MOTEUR.pop('anti_ombrage')  # ACAL606 : publié par la vue, pas le moteur


def _terrain(allee_m=None, kits=1):
    """T1-F1-027 : terrain 30 × 22 m, 25°, module 2,384 × 1,303 m, 2 par table,
    tel que ``ModeTerrain.helpers.js::demandeMoteur`` l'envoie."""
    contour = [[0, 0], [30, 0], [30, 22], [0, 22]]
    kit = {'code': 'terrain', 'libelle': 'Table terrain',
           'module_long_m': 2.384, 'module_court_m': 1.303,
           'puissance_module_wc': 710, 'inclinaison_deg': 25,
           'orientation': 'PORTRAIT', 'modules_par_table': 2, 'faitage_m': 0}
    parametres = {'kits': ['terrain'], 'axe_rangee': 'AUTO',
                  'mode_pose': 'rangees_explicites_dp', 'pas_recherche_m': 0.01}
    if allee_m is not None:
        parametres['allee_m'] = allee_m
    document = {
        'schema_version': 1, 'repere': 'TERRAIN', 'contour': contour,
        'surfaces': [{'type': 'polygone', 'repere': 'TERRAIN',
                      'contour': contour, 'trous': [], 'axe_rangee': 'AUTO',
                      'niveau': 0, 'pente_deg': 0, 'azimut_deg': 180,
                      'origine': [0, 0], 'coupures': []}],
        'kits': [kit] + [dict(kit, code='bis')] * (kits - 1),
        'parametres': parametres, 'obstacles': [], 'zones': []}
    if kits > 1:
        parametres['kits'] = ['terrain', 'bis']
    from apps.calepinage.moteur_io import deriver_axe_rangee
    return deriver_axe_rangee(document)


class PolitiqueDuSolTest(SimpleTestCase):
    """ACAL606 — champ au sol : entraxe anti-ombrage CALCULÉ à la latitude."""

    def test_sans_allee_anti_ombrage_a_la_latitude(self):
        from core.calepinage.politique_pas import (
            HEURE_SOLAIRE_DIMENSIONNEMENT, AntiOmbrage,
        )

        from apps.calepinage.moteur_service import politique_du_sol
        politique, bloc = politique_du_sol(_terrain(), {'latitude_deg': 30.4})
        self.assertIsInstance(politique, AntiOmbrage)
        self.assertEqual(politique.latitude_deg, 30.4)
        # Dimensionné à 10 h solaire au solstice, jamais « à midi ».
        self.assertEqual(politique.heure_solaire, HEURE_SOLAIRE_DIMENSIONNEMENT)
        self.assertEqual(HEURE_SOLAIRE_DIMENSIONNEMENT, 10.0)
        self.assertEqual(bloc, {
            'politique': 'ANTI_OMBRAGE', 'latitude_deg': 30.4,
            'entraxe_calcule_m': 5.922, 'vide_calcule_m': 1.601,
            'entraxe_applique_m': 5.922})

    def test_allee_saisie_garde_sa_pose_et_publie_l_ecart(self):
        from apps.calepinage.moteur_service import politique_du_sol
        politique, bloc = politique_du_sol(_terrain(0.6),
                                           {'latitude_deg': 30.4})
        self.assertIsNone(politique)
        self.assertEqual((bloc['politique'], bloc['entraxe_applique_m'],
                          bloc['entraxe_calcule_m']),
                         ('ALLEE_SAISIE', 4.921, 5.922))

    def test_contrat_porte_anti_ombrage_partout(self):
        for nom in ('exemple', 'exemple_vide', 'exemple_sol'):
            self.assertEqual(set(CONTRAT[nom]), set(CONTRAT['exemple']), nom)
        self.assertIsNone(CONTRAT['exemple']['anti_ombrage'])
        self.assertIsNone(CONTRAT['exemple_vide']['anti_ombrage'])

    def test_sans_sol_rien_ne_change(self):
        from apps.calepinage.moteur_service import politique_du_sol
        self.assertEqual(politique_du_sol(_terrain(), None), (None, None))

    def test_sol_sans_latitude_ou_deux_kits_refuse(self):
        from apps.calepinage.moteur_service import (
            erreurs_moteur_calepinage, politique_du_sol,
        )
        entree_invalide, _ = erreurs_moteur_calepinage()
        for document, sol, champ in ((_terrain(), {}, 'latitude_deg'),
                                     (_terrain(), {'latitude_deg': '30'},
                                      'latitude_deg'),
                                     (_terrain(kits=2), {'latitude_deg': 30.4},
                                      'kits')):
            with self.subTest(sol=sol, champ=champ):
                with self.assertRaises(entree_invalide) as refus:
                    politique_du_sol(document, sol)
                self.assertIn(champ, str(refus.exception))

    def test_moteur_reel_132_modules_jamais_176(self):
        """Sans mock : le terrain pose 3 rangées à 5,922 m, pas 4 à 0,60 m."""
        from apps.calepinage.moteur_service import (
            calepinage_json, politique_du_sol,
        )
        document = _terrain()
        politique, _bloc = politique_du_sol(document, {'latitude_deg': 30.4})
        pose = calepinage_json(document, company=1, suggestions=False,
                               politique=politique)
        self.assertEqual(pose['total_modules'], 132)
        sans_sol = calepinage_json(document, company=1, suggestions=False)
        self.assertEqual(sans_sol['total_modules'], 176)


class PortePoseTest(BaseApiCalepinage):
    def _appeler(self, api, corps, *, sortie=None, erreur=None):
        with mock.patch('apps.calepinage.moteur_service.calepinage_json',
                        side_effect=erreur,
                        return_value=dict(sortie or SORTIE_MOTEUR)) as porte:
            reponse = api.post(URL, corps, format='json')
        self.porte = porte
        return reponse

    def test_la_reponse_porte_exactement_les_cles_du_contrat(self):
        reponse = self._appeler(self.api, {'demande': CONTRAT['demande']})

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(set(reponse.data), set(CONTRAT['exemple']),
                         'la réponse et contract_samples/pose.json ont '
                         'divergé — PACT10')

    def test_le_releve_voyage_sous_demande(self):
        reponse = self._appeler(self.api, {'demande': CONTRAT['demande']})

        self.assertEqual(reponse.status_code, 200, reponse.data)
        document = self.porte.call_args.args[0]
        self.assertEqual(document['repere'], CONTRAT['demande']['repere'])

    def test_les_suggestions_ne_sont_pas_payees(self):
        """La pose ne les publie pas : les calculer serait du travail perdu."""
        self._appeler(self.api, {'demande': CONTRAT['demande']})

        # ACAL292 — le paramètre ``tiroirs`` n'existe plus.
        self.assertNotIn('tiroirs', self.porte.call_args.kwargs)
        self.assertIs(self.porte.call_args.kwargs['suggestions'], False)

    def test_corps_vide_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(URL, {}, format='json')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('demande', reponse.data)

    def test_releve_refuse_par_le_moteur_rend_409_avec_le_motif_serveur(self):
        from apps.calepinage.moteur_service import (
            erreurs_moteur_calepinage,
        )

        entree_invalide, _ = erreurs_moteur_calepinage()
        reponse = self._appeler(self.api, {'demande': CONTRAT['demande']},
                                erreur=entree_invalide('Surface absente.'))

        self.assertEqual(reponse.status_code, 409)
        self.assertIn('demande', reponse.data)
        self.assertIn('Surface absente.', str(reponse.data['demande']))

    def test_axe_auto_est_derive_avant_le_moteur(self):
        """ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD — ``AUTO`` n'atteint jamais le
        moteur : la porte le remplace par l'axe IMPOSÉ par le kit."""
        from .test_axe_rangee_auto import _demande

        reponse = self._appeler(self.api, {'demande': _demande(1, 180)})

        self.assertEqual(reponse.status_code, 200, reponse.data)
        document = self.porte.call_args.args[0]
        self.assertEqual(document['parametres']['axe_rangee'], 'EST_OUEST')
        self.assertEqual(document['surfaces'][0]['axe_rangee'], 'EST_OUEST')

    def test_sol_sans_allee_passe_l_anti_ombrage_au_moteur(self):
        """ACAL606 — la porte transmet la politique et publie le bloc."""
        from core.calepinage.politique_pas import AntiOmbrage

        reponse = self._appeler(self.api, {'demande': _terrain(),
                                           'sol': {'latitude_deg': 30.4}})

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsInstance(self.porte.call_args.kwargs['politique'],
                              AntiOmbrage)
        self.assertEqual(reponse.data['anti_ombrage'],
                         CONTRAT['exemple_sol']['anti_ombrage'])

    def test_sans_sol_politique_none_et_bloc_null(self):
        reponse = self._appeler(self.api, {'demande': CONTRAT['demande']})

        self.assertIsNone(self.porte.call_args.kwargs['politique'])
        self.assertIsNone(reponse.data['anti_ombrage'])

    def test_sol_sans_latitude_409_nommant_le_champ(self):
        reponse = self._appeler(self.api, {'demande': _terrain(), 'sol': {}})

        self.assertEqual(reponse.status_code, 409)
        self.assertIn('latitude_deg', str(reponse.data['demande']))

    def test_sans_calepinage_gerer_403(self):
        reponse = self._appeler(self.api_sans, {'demande': CONTRAT['demande']})

        self.assertEqual(reponse.status_code, 403)

    def test_la_route_n_est_pas_gardee_par_ao(self):
        self.assertEqual(MoteurPoseView.write_permission, 'calepinage_gerer')
        self.assertEqual(MoteurPoseView.read_permission, 'calepinage_voir')


class VerdictTest(SimpleTestCase):
    """Le verdict est GÉNÉRÉ des grandeurs mesurées — jamais rédigé.

    ``SimpleTestCase`` : ``verdict_de_pose`` est une fonction PURE (elle lit
    un dictionnaire, elle n'ouvre aucune ligne) — lui donner une base serait
    payer une base pour rien.
    """

    def test_pose_optimale_dit_le_compte_et_l_optimum(self):
        verdict = verdict_de_pose(CONTRAT['exemple'])

        self.assertIn('12', verdict)
        self.assertIn('optimum prouvé', verdict)

    def test_optimum_non_prouve_le_dit_et_donne_la_borne(self):
        resultat = dict(CONTRAT['exemple'], total_modules=9)
        resultat['preuve'] = dict(CONTRAT['exemple']['preuve'],
                                  optimal=False, borne_superieure=11)

        verdict = verdict_de_pose(resultat)

        self.assertIn('NON prouvé', verdict)
        self.assertIn('11', verdict)

    def test_aucun_module_reprend_le_libelle_du_moteur(self):
        """La RAISON vient du moteur : on n'en invente jamais une."""
        verdict = verdict_de_pose(CONTRAT['exemple_vide'])

        self.assertEqual(verdict,
                         CONTRAT['exemple_vide']['preuve']['libelle'])

    def test_aucun_module_sans_libelle_reste_une_phrase_neutre(self):
        resultat = dict(CONTRAT['exemple_vide'])
        resultat['preuve'] = dict(CONTRAT['exemple_vide']['preuve'],
                                  libelle='')

        self.assertEqual(verdict_de_pose(resultat),
                         'Aucun module posable sur ce relevé.')
