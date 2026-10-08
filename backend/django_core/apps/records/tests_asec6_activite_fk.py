"""ASEC6 — ``Activity.assigned_to`` / ``activity_type`` bornés à la société.

Un id d'une autre société (utilisateur, type d'activité, type suivant de
l'enchaînement) donne 400 sans écriture ni libellé étranger renvoyé ; un id
inexistant donne 400 (jamais 500) ; les ids de la société passent inchangés.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.records.models import Activity, ActivityType
from authentication.models import Company

User = get_user_model()
URL = '/api/django/records/activities/'


class ActiviteFkSocieteTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='ASEC6 A', slug='asec6-a')
        self.co_b = Company.objects.create(nom='ASEC6 B', slug='asec6-b')
        self.resp_a = User.objects.create_user(
            username='asec6_resp_a', password='x', role_legacy='responsable',
            company=self.co_a)
        self.collegue_a = User.objects.create_user(
            username='asec6_col_a', password='x', role_legacy='normal',
            company=self.co_a)
        self.user_b = User.objects.create_user(
            username='asec6_user_b_secret', password='x',
            role_legacy='normal', company=self.co_b)
        self.type_a = ActivityType.objects.create(company=self.co_a, nom='Appel A')
        self.type_b = ActivityType.objects.create(
            company=self.co_b, nom='Type B secret')
        self.api = APIClient()
        self.api.force_authenticate(self.resp_a)

    def _activite(self, **kw):
        valeurs = dict(company=self.co_a, content_type=None, object_id=None,
                       personnelle=True, activity_type=self.type_a,
                       summary='A faire', assigned_to=self.resp_a,
                       created_by=self.resp_a)
        valeurs.update(kw)
        return Activity.objects.create(**valeurs)

    def _sans_fuite(self, resp):
        texte = str(resp.data)
        self.assertNotIn('asec6_user_b_secret', texte)
        self.assertNotIn('Type B secret', texte)

    def test_creation_assigned_to_etranger_400(self):
        avant = Activity.objects.count()
        resp = self.api.post(URL, {'summary': 'x', 'assigned_to': self.user_b.id,
                                   'activity_type': self.type_a.id},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('assigned_to', resp.data)
        self._sans_fuite(resp)
        self.assertEqual(Activity.objects.count(), avant)

    def test_patch_activity_type_etranger_400(self):
        act = self._activite()
        for champ, valeur in (('activity_type', self.type_b.id),
                              ('assigned_to', self.user_b.id)):
            with self.subTest(champ=champ):
                resp = self.api.patch(f'{URL}{act.id}/', {champ: valeur},
                                      format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn(champ, resp.data)
                self._sans_fuite(resp)
        act.refresh_from_db()
        self.assertEqual(act.activity_type_id, self.type_a.id)
        self.assertEqual(act.assigned_to_id, self.resp_a.id)

    def test_done_type_suivant_etranger_400(self):
        ActivityType.objects.filter(pk=self.type_a.pk).update(
            type_suivant=self.type_b,
            mode_enchainement=ActivityType.ModeEnchainement.DECLENCHER)
        act = self._activite()
        avant = Activity.objects.count()
        resp = self.api.post(f'{URL}{act.id}/done/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self._sans_fuite(resp)
        act.refresh_from_db()
        self.assertFalse(act.done)
        self.assertEqual(Activity.objects.count(), avant)
        # La suite demandée explicitement vers un type de B : refusée aussi.
        ActivityType.objects.filter(pk=self.type_a.pk).update(
            type_suivant=None,
            mode_enchainement=ActivityType.ModeEnchainement.AUCUN)
        resp = self.api.post(f'{URL}{act.id}/done/',
                             {'next': {'activity_type': self.type_b.id}},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        act.refresh_from_db()
        self.assertFalse(act.done)

    def test_id_inexistant_400_pas_500(self):
        resp = self.api.post(URL, {'summary': 'x', 'assigned_to': 999999999},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        act = self._activite()
        resp = self.api.post(f'{URL}{act.id}/done/',
                             {'next': {'activity_type': 999999999}},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_ids_societe_ok(self):
        resp = self.api.post(URL, {'summary': 'x',
                                   'assigned_to': self.collegue_a.id,
                                   'activity_type': self.type_a.id},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        act = self._activite()
        resp = self.api.patch(f'{URL}{act.id}/',
                              {'assigned_to': self.collegue_a.id},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self.api.post(f'{URL}{act.id}/done/',
                             {'next': {'activity_type': self.type_a.id}},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
