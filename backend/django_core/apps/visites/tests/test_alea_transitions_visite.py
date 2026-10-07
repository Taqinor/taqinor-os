"""ALEA6 — la table ``TRANSITIONS`` des statuts de visite, appliquée SERVEUR.

Rejoue la sonde V4 LVIS-2 : un POST direct sur ``valider`` d'un brouillon
vide rendait 200 et posait le feu vert sur 20 éléments manquants.
"""
from apps.crm.models import Lead
from apps.visites import selectors, services
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase, auth

URL = '/api/django/visites/visites/{}/{}/'
RENVOI = {'photos': [], 'mesures': [], 'motif': 'Reprendre.'}


class TransitionsVisiteTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.api_bureau = auth(self.bureau)

    def _etat(self, visite_id):
        visite = VisiteTerrain.objects.get(pk=visite_id)
        return (visite.statut, visite.validee_le, visite.validee_par_id)

    def _terminee_complete(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        resp = self.api.post(URL.format(visite_id, 'terminer'), {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return visite_id

    def _assert_feu_vert_absent(self, visite_id):
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertIsNone(visite.validee_le)
        self.assertIsNone(visite.validee_par_id)
        self.assertFalse(Lead.objects.get(pk=self.lead.pk).visite_effectuee)
        self.assertIsNone(
            selectors.releve_pour_calepinage(self.lead)['visite_id'])

    def test_valider_brouillon_refuse(self):
        visite_id = self.creer_visite()
        avant = self._etat(visite_id)
        resp = self.api_bureau.post(URL.format(visite_id, 'valider'), {},
                                    format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['statut'],
                         ['La visite doit être terminée avant validation.'])
        # Persistance : rien n'a bougé.
        self.assertEqual(self._etat(visite_id), avant)
        self._assert_feu_vert_absent(visite_id)

    def test_valider_incomplete_refuse(self):
        visite_id = self._terminee_complete()
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        slot = next(s for cat in detail.data['checklist']
                    for s in cat['slots'] if s['code'] == 'general_facade')
        media_id = slot['photos'][0]['id']
        supprime = self.api.delete(
            f'/api/django/visites/visites/{visite_id}/photos/{media_id}/')
        self.assertEqual(supprime.status_code, 200, supprime.data)
        avant = self._etat(visite_id)
        self.assertEqual(avant[0], VisiteTerrain.Statut.TERMINEE)

        resp = self.api_bureau.post(URL.format(visite_id, 'valider'), {},
                                    format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        attendus = selectors.visite_terrain_manquants(
            VisiteTerrain.objects.get(pk=visite_id))
        self.assertTrue(attendus)
        self.assertEqual(resp.data['manquants'], attendus)
        self.assertEqual(self._etat(visite_id), avant)
        self._assert_feu_vert_absent(visite_id)

    def test_renvoyer_brouillon_refuse(self):
        visite_id = self.creer_visite()
        avant = self._etat(visite_id)
        resp = self.api_bureau.post(URL.format(visite_id, 'renvoyer'), RENVOI,
                                    format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('statut', resp.data)
        self.assertEqual(self._etat(visite_id), avant)

    def test_terminee_complete_se_valide(self):
        visite_id = self._terminee_complete()
        resp = self.api_bureau.post(URL.format(visite_id, 'valider'), {},
                                    format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], VisiteTerrain.Statut.VALIDEE)

    def test_toutes_paires_hors_table_refusees(self):
        for statut in VisiteTerrain.Statut.values:
            for action, corps in (('valider', {}), ('renvoyer', RENVOI)):
                if statut in services.TRANSITIONS[action]:
                    continue
                with self.subTest(statut=statut, action=action):
                    visite = VisiteTerrain.objects.create(
                        company=self.company, lead=self.lead,
                        commercial=self.commercial, statut=statut)
                    resp = self.api_bureau.post(
                        URL.format(visite.id, action), corps, format='json')
                    self.assertEqual(resp.status_code, 400, resp.data)
                    self.assertIn('statut', resp.data)
                    visite.refresh_from_db()
                    self.assertEqual(visite.statut, statut)
