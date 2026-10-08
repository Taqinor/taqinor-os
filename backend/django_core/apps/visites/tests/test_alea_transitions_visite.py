"""ALEA6 — la table ``TRANSITIONS`` des statuts de visite, appliquée SERVEUR.

Rejoue la sonde V4 LVIS-2 : un POST direct sur ``valider`` d'un brouillon
vide rendait 200 et posait le feu vert sur 20 éléments manquants.
"""
from apps.crm.models import Lead, LeadActivity
from apps.visites import selectors, services
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_cadence_terrain import (
    QUALIFICATION_VALIDE)
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

    def _effectuee(self):
        return Lead.objects.get(pk=self.lead.pk).visite_effectuee

    def _assert_feu_vert_absent(self, visite_id, effectuee_avant):
        # ``Lead.visite_effectuee`` garde le sens « visite réalisée » : il est
        # posé dès ``terminer`` (VISITE-CADENCE) — le feu vert refusé ne doit
        # simplement pas le faire bouger.
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertIsNone(visite.validee_le)
        self.assertIsNone(visite.validee_par_id)
        self.assertEqual(self._effectuee(), effectuee_avant)
        self.assertIsNone(
            selectors.releve_pour_calepinage(self.lead)['visite_id'])

    def test_valider_brouillon_refuse(self):
        visite_id = self.creer_visite()
        avant = self._etat(visite_id)
        self.assertFalse(self._effectuee())
        resp = self.api_bureau.post(URL.format(visite_id, 'valider'), {},
                                    format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['statut'],
                         ['La visite doit être terminée avant validation.'])
        # Persistance : rien n'a bougé.
        self.assertEqual(self._etat(visite_id), avant)
        self._assert_feu_vert_absent(visite_id, effectuee_avant=False)

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
        effectuee_avant = self._effectuee()

        resp = self.api_bureau.post(URL.format(visite_id, 'valider'), {},
                                    format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        attendus = selectors.visite_terrain_manquants(
            VisiteTerrain.objects.get(pk=visite_id))
        self.assertTrue(attendus)
        self.assertEqual(resp.data['manquants'], attendus)
        self.assertEqual(self._etat(visite_id), avant)
        self._assert_feu_vert_absent(visite_id, effectuee_avant)

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


class QualificationApresTermineeTests(VisiteTerrainBase):
    """ALEA7 — rejoue la sonde V4 LVIS-7 : la qualification d'une visite
    TERMINÉE se réécrivait en 200 et le chatter du lead restait périmé."""

    MESSAGE = ("Visite terminée : demandez un renvoi au bureau d'études "
               'pour corriger.')

    def _qualifier(self, visite_id, **valeurs):
        return self.api.post(URL.format(visite_id, 'qualification'),
                             dict(QUALIFICATION_VALIDE, **valeurs),
                             format='json')

    def _terminee_qualifiee_chaud(self):
        visite_id = self.creer_visite()
        self.remplir(visite_id)
        resp = self._qualifier(visite_id, temperature='chaud')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self.api.patch(f'/api/django/visites/visites/{visite_id}/',
                              {'notes': 'Toiture saine.'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self.api.post(URL.format(visite_id, 'terminer'), {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return visite_id

    def test_qualification_terminee_refusee(self):
        visite_id = self._terminee_qualifiee_chaud()
        resp = self.api.post(URL.format(visite_id, 'qualification'),
                             {'temperature': 'froid'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['statut'], [self.MESSAGE])
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.qualification['temperature'], 'chaud')
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='Client froid').exists())

    def test_notes_terminee_refusees(self):
        visite_id = self._terminee_qualifiee_chaud()
        resp = self.api.patch(f'/api/django/visites/visites/{visite_id}/',
                              {'notes': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['statut'], [self.MESSAGE])
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.notes, 'Toiture saine.')

    def test_qualification_a_refaire_acceptee(self):
        visite_id = self._terminee_qualifiee_chaud()
        renvoi = auth(self.bureau).post(URL.format(visite_id, 'renvoyer'),
                                        RENVOI, format='json')
        self.assertEqual(renvoi.status_code, 200, renvoi.data)
        resp = self._qualifier(visite_id, temperature='froid')
        self.assertEqual(resp.status_code, 200, resp.data)
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertEqual(visite.qualification['temperature'], 'froid')

    def test_qualification_brouillon_acceptee(self):
        visite_id = self.creer_visite()
        resp = self._qualifier(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)
