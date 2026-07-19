"""PUB90 — Tests du feedback utile/faux-positif + précision + throttle brake-only.

Prouve : (1) un vote utile/faux-positif est stocké (acteur + horodatage serveur) ;
(2) la précision par détecteur est calculée ; (3) un détecteur voté inutile 5×
devient ``throttled`` (VISIBLE) et sa cadence est réduite (record_anomaly freine
les enregistrements redondants dans la fenêtre), SANS jamais lever d'alerte auto.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import anomaly
from apps.adsengine.models import AnomalyEvent

User = get_user_model()


def _fired(detector='cpl_band'):
    return anomaly.Detection(
        detector=detector, fired=True, insufficient_data=False,
        severity=anomaly.SEVERITY_WARNING, kind='cost_spike',
        message_fr='Coût par lead hors bande.', computed={'ratio': 3.0})


class AnomalyFeedbackModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='FB Co', slug='fb-co')

    def _anomaly(self, detector='cpl_band', feedback=''):
        return AnomalyEvent.objects.create(
            company=self.company, kind='cost_spike', detector=detector,
            severity='warning', feedback=feedback)

    def test_record_anomaly_stores_detector(self):
        ev = anomaly.record_anomaly(self.company, _fired('cpl_band'))
        self.assertIsNotNone(ev)
        self.assertEqual(ev.detector, 'cpl_band')

    def test_precision_per_detector(self):
        self._anomaly(feedback=AnomalyEvent.Feedback.UTILE)
        self._anomaly(feedback=AnomalyEvent.Feedback.UTILE)
        self._anomaly(feedback=AnomalyEvent.Feedback.FAUX_POSITIF)
        stats = anomaly.detector_stats(self.company, 'cpl_band')
        self.assertEqual(stats['labelled'], 3)
        self.assertEqual(stats['useful'], 2)
        self.assertEqual(stats['false_positive'], 1)
        self.assertAlmostEqual(stats['precision'], 2 / 3, places=3)
        self.assertFalse(stats['throttled'])

    def test_precision_none_without_votes(self):
        self._anomaly()
        stats = anomaly.detector_stats(self.company, 'cpl_band')
        self.assertIsNone(stats['precision'])

    def test_five_false_positives_throttles_detector(self):
        for _ in range(5):
            self._anomaly(feedback=AnomalyEvent.Feedback.FAUX_POSITIF)
        self.assertTrue(
            anomaly.is_detector_throttled(self.company, 'cpl_band'))
        stats = anomaly.detector_stats(self.company, 'cpl_band')
        self.assertTrue(stats['throttled'])
        self.assertGreater(stats['throttle_factor'], 1)

    def test_four_false_positives_not_yet_throttled(self):
        for _ in range(4):
            self._anomaly(feedback=AnomalyEvent.Feedback.FAUX_POSITIF)
        self.assertFalse(
            anomaly.is_detector_throttled(self.company, 'cpl_band'))

    def test_throttled_detector_cadence_reduced_brake_only(self):
        # 5 faux positifs récents → throttlé ; une anomalie du même détecteur
        # existe déjà dans la fenêtre → nouvel enregistrement FREINÉ (None).
        for _ in range(5):
            self._anomaly(feedback=AnomalyEvent.Feedback.FAUX_POSITIF)
        before = AnomalyEvent.objects.filter(detector='cpl_band').count()
        result = anomaly.record_anomaly(self.company, _fired('cpl_band'))
        self.assertIsNone(result)  # freiné, jamais une nouvelle alerte
        self.assertEqual(
            AnomalyEvent.objects.filter(detector='cpl_band').count(), before)

    def test_throttled_detector_still_records_once_per_window(self):
        for _ in range(5):
            self._anomaly(feedback=AnomalyEvent.Feedback.FAUX_POSITIF)
        # Hors de la fenêtre de throttle (2 jours plus tard) → un enregistrement
        # est de nouveau permis : cadence RÉDUITE, pas supprimée.
        later = timezone.now() + datetime.timedelta(days=2)
        result = anomaly.record_anomaly(
            self.company, _fired('cpl_band'), now=later)
        self.assertIsNotNone(result)

    def test_non_throttled_detector_always_records(self):
        result = anomaly.record_anomaly(self.company, _fired('spend_vs_median'))
        self.assertIsNotNone(result)


class AnomalyFeedbackEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='FBE Co', slug='fbe-co')
        self.ev = AnomalyEvent.objects.create(
            company=self.company, kind='cost_spike', detector='cpl_band',
            severity='warning')

    def _api(self, perms):
        role = Role.objects.create(
            company=self.company, nom='r-' + perms[0], permissions=perms)
        user = User.objects.create_user(
            username='u-' + perms[0], password='x', company=self.company,
            role_legacy='normal', role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api, user

    def test_feedback_vote_stored_with_actor(self):
        api, user = self._api(['adsengine_manage', 'adsengine_view'])
        resp = api.post(
            f'/api/django/adsengine/anomalies/{self.ev.pk}/feedback/',
            {'vote': 'false_positive'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.feedback, 'false_positive')
        self.assertEqual(self.ev.feedback_by, user)
        self.assertIsNotNone(self.ev.feedback_at)

    def test_feedback_rejects_invalid_vote(self):
        api, _ = self._api(['adsengine_manage', 'adsengine_view'])
        resp = api.post(
            f'/api/django/adsengine/anomalies/{self.ev.pk}/feedback/',
            {'vote': 'peut_etre'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_detectors_endpoint_shows_throttle(self):
        for _ in range(5):
            AnomalyEvent.objects.create(
                company=self.company, kind='cost_spike', detector='cpl_band',
                severity='warning', feedback='false_positive')
        api, _ = self._api(['adsengine_view'])
        resp = api.get('/api/django/adsengine/anomalies/detecteurs/')
        self.assertEqual(resp.status_code, 200)
        by = {d['detector']: d for d in resp.data['detecteurs']}
        self.assertIn('cpl_band', by)
        self.assertTrue(by['cpl_band']['throttled'])
