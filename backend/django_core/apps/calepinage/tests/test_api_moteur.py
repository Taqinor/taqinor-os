"""CAL22 — la porte NEUTRE du moteur : `POST /calepinage/moteur/calculer/`.

Ce qui est prouvé ici :

* la route est gardée par ``calepinage_gerer`` (et PAS par ``ao_gerer``) : un
  module autonome n'emprunte plus la porte d'un autre domaine ;
* une entrée INVALIDE rend 400 avec le champ fautif NOMMÉ et le motif français
  du serveur — jamais un 500 ;
* le corps accepte l'enveloppe ``{"entree": …}`` et le document nu ;
* la sortie est celle du moteur du dépôt (``moteur_service.calepinage_json``,
  la MÊME sérialisation que la porte AO), plus ``depuis_cache`` ;
* au-delà du budget synchrone, la route rend 202 avec le coût estimé — elle ne
  fait jamais attendre devant un écran gelé.

Le MOTEUR lui-même n'est pas retesté ici (il a ses propres tests dans
``core/calepinage`` et ``apps/ao``) : ce fichier prouve la PORTE.

Run :
    python manage.py test apps.calepinage.tests.test_api_moteur -v2
"""
from unittest import mock

from .test_api_liste import BaseApiCalepinage

URL = '/api/django/calepinage/moteur/calculer/'

DOCUMENT = {
    'repere': 'SITE-ESSAI',
    'surfaces': [{'repere': 'PAN-A',
                  'contour': [[0, 0], [10, 0], [10, 6], [0, 6]]}],
    'kits': [{'code': 'portrait', 'largeur_m': 1.14, 'hauteur_m': 2.28,
              'puissance_module_wc': 720}],
    'parametres': {'kit_par_defaut': 'portrait'},
}

SORTIE = {'schema_version': 1, 'repere': 'SITE-ESSAI', 'total_modules': 12,
          'kwc': 8.64}


class CoutFactice:
    def __init__(self, synchrone=True):
        self.synchrone = synchrone
        self.positions, self.kits, self.appels = 10, 1, 10
        self.millisecondes, self.motif = 12.5, 'essai'


class PorteMoteurTest(BaseApiCalepinage):
    def _appeler(self, api, corps, *, cout=None, sortie=None, erreur=None):
        """Appelle la PORTE — le moteur lui-même est simulé (il a ses tests)."""
        with mock.patch('apps.calepinage.moteur_service.cout_calepinage',
                        return_value=cout or CoutFactice()), \
                mock.patch('apps.calepinage.moteur_service.calepinage_json',
                           side_effect=erreur,
                           return_value=dict(sortie or SORTIE)):
            return api.post(URL, corps, format='json')

    def test_enveloppe_et_document_nu_acceptes(self):
        for corps in (DOCUMENT, {'entree': DOCUMENT}):
            with self.subTest(corps=list(corps)[0]):
                reponse = self._appeler(self.api, corps)
                self.assertEqual(reponse.status_code, 200, reponse.data)
                self.assertFalse(reponse.data['depuis_cache'])
                self.assertEqual(reponse.data['total_modules'], 12)

    def test_corps_vide_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(URL, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('entree', reponse.data)

    def test_entree_invalide_rend_400_avec_le_motif_serveur(self):
        from apps.calepinage.moteur_service import (
            erreurs_moteur_calepinage,
        )

        entree_invalide, _ = erreurs_moteur_calepinage()
        with mock.patch('apps.calepinage.moteur_service.cout_calepinage',
                        side_effect=entree_invalide('Surface absente.')):
            reponse = self.api.post(URL, DOCUMENT, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('entree', reponse.data)
        self.assertIn('Surface absente.', str(reponse.data['entree']))

    def test_au_dela_du_budget_rend_202_avec_le_cout(self):
        reponse = self._appeler(self.api, DOCUMENT,
                                cout=CoutFactice(synchrone=False))
        self.assertEqual(reponse.status_code, 202)
        self.assertIn('cout_estime', reponse.data)
        self.assertEqual(reponse.data['cout_estime']['motif'], 'essai')

    def test_sans_calepinage_gerer_403(self):
        reponse = self._appeler(self.api_sans, DOCUMENT)
        self.assertEqual(reponse.status_code, 403)

    def test_la_route_n_est_pas_gardee_par_ao(self):
        """Un porteur de ``calepinage_gerer`` SANS droits AO passe."""
        from apps.calepinage.views.moteur import MoteurCalculerView

        self.assertEqual(MoteurCalculerView.write_permission,
                         'calepinage_gerer')
        self.assertEqual(MoteurCalculerView.read_permission,
                         'calepinage_voir')
