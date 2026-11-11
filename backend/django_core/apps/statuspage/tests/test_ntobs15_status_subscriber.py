"""NTOBS15 — abonnement aux notifications d'incidents (e-mail à l'ouverture/
résolution) pour la page de statut publique."""
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from ..models import IncidentPublic, StatusSubscriber


class PublicAbonnerTest(TestCase):
    def test_subscribing_creates_unconfirmed_subscriber_and_sends_email(self):
        resp = APIClient().post(
            '/api/django/statuspage/public/abonner/', {'email': 'a@example.com'})
        self.assertEqual(resp.status_code, 202)
        abonne = StatusSubscriber.objects.get(email='a@example.com')
        self.assertFalse(abonne.confirme)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('confirmer', mail.outbox[0].body)

    def test_invalid_email_rejected(self):
        resp = APIClient().post(
            '/api/django/statuspage/public/abonner/', {'email': 'pas-un-email'})
        self.assertEqual(resp.status_code, 400)


class PublicConfirmerTest(TestCase):
    def test_valid_token_confirms(self):
        abonne = StatusSubscriber.objects.create(email='b@example.com')
        resp = APIClient().get(
            f'/api/django/statuspage/public/confirmer/{abonne.token_desabonnement}/')
        self.assertEqual(resp.status_code, 200)
        abonne.refresh_from_db()
        self.assertTrue(abonne.confirme)

    def test_unknown_token_is_404(self):
        resp = APIClient().get('/api/django/statuspage/public/confirmer/bogus/')
        self.assertEqual(resp.status_code, 404)


class PublicDesabonnerTest(TestCase):
    def test_valid_token_unsubscribes_without_auth(self):
        # APUB49 — le POST désabonne (le GET ne fait que confirmer).
        abonne = StatusSubscriber.objects.create(
            email='c@example.com', confirme=True)
        resp = APIClient().post(
            f'/api/django/statuspage/public/desabonner/{abonne.token_desabonnement}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            StatusSubscriber.objects.filter(email='c@example.com').exists())

    @override_settings(PUBLIC_BASE_URL='https://api.taqinor.ma')
    def test_lien_absolu_et_get_ne_desabonne_pas(self):
        """APUB49 — l'e-mail porte un lien ABSOLU ; GET = confirmation sans
        effet (noindex) ; POST du même jeton = désabonnement."""
        abonne = StatusSubscriber.objects.create(email='f@example.com', confirme=True)
        mail.outbox.clear()
        IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        chemin = f'/api/django/statuspage/public/desabonner/{abonne.token_desabonnement}/'
        self.assertIn(f'Se désabonner : https://api.taqinor.ma{chemin}', mail.outbox[0].body)
        page = APIClient().get(chemin)
        self.assertEqual(page.status_code, 200)
        self.assertIn('method="post"', page.content.decode())
        self.assertIn('noindex', page.content.decode())
        self.assertTrue(StatusSubscriber.objects.filter(pk=abonne.pk).exists())
        resp = APIClient().post(chemin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['detail'], 'Désabonnement effectué.')
        self.assertFalse(StatusSubscriber.objects.filter(pk=abonne.pk).exists())
        self.assertEqual(APIClient().get(chemin).status_code, 404)

    @override_settings(PUBLIC_BASE_URL='')
    def test_sans_base_publique_ligne_omise(self):
        StatusSubscriber.objects.create(email='g@example.com', confirme=True)
        mail.outbox.clear()
        IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        self.assertNotIn('désabonner', mail.outbox[0].body)

    def test_unknown_token_is_404(self):
        resp = APIClient().get('/api/django/statuspage/public/desabonner/bogus/')
        self.assertEqual(resp.status_code, 404)


class IncidentNotificationTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_confirmed_subscriber_notified_on_incident_opened(self):
        StatusSubscriber.objects.create(email='d@example.com', confirme=True)
        IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['d@example.com'])

    def test_unconfirmed_subscriber_never_notified(self):
        StatusSubscriber.objects.create(email='e@example.com', confirme=False)
        IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        self.assertEqual(len(mail.outbox), 0)

    def test_notified_again_on_resolution(self):
        StatusSubscriber.objects.create(email='f@example.com', confirme=True)
        incident = IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now())
        mail.outbox.clear()
        incident.statut = IncidentPublic.Statut.RESOLVED
        incident.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Résolu', mail.outbox[0].subject)

    def test_resolving_twice_does_not_double_notify(self):
        StatusSubscriber.objects.create(email='g@example.com', confirme=True)
        incident = IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=timezone.now(),
            statut=IncidentPublic.Statut.RESOLVED)
        mail.outbox.clear()
        incident.description = 'update sans changement de statut'
        incident.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_region_filter_only_matches_its_own_region(self):
        StatusSubscriber.objects.create(
            email='eu@example.com', confirme=True, region_filtre='EU-West')
        StatusSubscriber.objects.create(
            email='all@example.com', confirme=True, region_filtre='')
        IncidentPublic.objects.create(
            titre='Panne région US', company=None, region='US-East',
            debute_le=timezone.now())
        destinataires = [m.to[0] for m in mail.outbox]
        self.assertIn('all@example.com', destinataires)
        self.assertNotIn('eu@example.com', destinataires)

    def test_company_specific_incident_never_notifies_public_subscribers(self):
        company = Company.objects.create(nom='Acme', slug='acme-ntobs15')
        StatusSubscriber.objects.create(email='h@example.com', confirme=True)
        IncidentPublic.objects.create(
            titre='Incident société', company=company, debute_le=timezone.now())
        self.assertEqual(len(mail.outbox), 0)
