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
  demande ni tiroirs ni suggestions — on ne paye pas ce qu'on ne publie pas ;
* le ``verdict`` est GÉNÉRÉ des grandeurs mesurées, jamais rédigé ;
* un relevé invalide rend 400 en NOMMANT le champ fautif, jamais un 500 ;
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
    rangees=[], tiroirs={}, suggestions=[])
SORTIE_MOTEUR.pop('verdict')


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

    def test_ni_tiroirs_ni_suggestions_ne_sont_payes(self):
        """La pose ne les publie pas : les calculer serait du travail perdu."""
        self._appeler(self.api, {'demande': CONTRAT['demande']})

        self.assertIs(self.porte.call_args.kwargs['tiroirs'], False)
        self.assertIs(self.porte.call_args.kwargs['suggestions'], False)

    def test_corps_vide_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(URL, {}, format='json')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('demande', reponse.data)

    def test_releve_invalide_rend_400_avec_le_motif_serveur(self):
        from apps.calepinage.moteur_service import (
            erreurs_moteur_calepinage,
        )

        entree_invalide, _ = erreurs_moteur_calepinage()
        reponse = self._appeler(self.api, {'demande': CONTRAT['demande']},
                                erreur=entree_invalide('Surface absente.'))

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('demande', reponse.data)
        self.assertIn('Surface absente.', str(reponse.data['demande']))

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
