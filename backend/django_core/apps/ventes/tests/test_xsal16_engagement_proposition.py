"""XSAL16 — Analytics d'engagement par section de la proposition web (backend).

L'émission des beacons depuis la page proposition (site web) est HORS
PÉRIMÈTRE ERP (docs/WEB_PLAN.md) — cette suite couvre uniquement
l'enregistrement backend + l'affichage vendeur (Devis.engagement).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal16_engagement_proposition -v 2
"""
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, DevisActivity, ShareLink

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class EngagementBeaconTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = _company('xsal16-co')
        self.user = User.objects.create_user(
            username='xsal16user', password='x', company=self.company,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alami', telephone='0612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-XSAL16-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            created_by=self.user)
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _post(self, token=None, body=None):
        token = token or self.link.token
        return self.api.post(
            f'/api/django/public/proposal/{token}/engagement/',
            body or {}, format='json')

    def test_beacon_registers_on_correct_token(self):
        resp = self._post(body={'section': 'prix', 'seconds': 30})
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertEqual(self.link.engagement['prix']['seconds'], 30)
        self.assertEqual(self.link.engagement['prix']['hits'], 1)

    def test_beacon_accumulates_across_calls(self):
        self._post(body={'section': 'prix', 'seconds': 10})
        self._post(body={'section': 'prix', 'seconds': 15})
        self.link.refresh_from_db()
        self.assertEqual(self.link.engagement['prix']['seconds'], 25)
        self.assertEqual(self.link.engagement['prix']['hits'], 2)

    def test_multiple_sections_tracked_independently(self):
        self._post(body={'section': 'prix', 'seconds': 30})
        self._post(body={'section': 'etude', 'seconds': 5})
        self.link.refresh_from_db()
        self.assertIn('prix', self.link.engagement)
        self.assertIn('etude', self.link.engagement)
        self.assertEqual(self.link.engagement['etude']['seconds'], 5)

    def test_unknown_section_silently_ignored(self):
        resp = self._post(body={'section': 'bogus', 'seconds': 30})
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertEqual(self.link.engagement or {}, {})

    def test_zero_or_invalid_seconds_ignored(self):
        self._post(body={'section': 'prix', 'seconds': 0})
        self._post(body={'section': 'prix', 'seconds': 'abc'})
        self.link.refresh_from_db()
        self.assertEqual(self.link.engagement or {}, {})

    def test_invalid_token_returns_404(self):
        resp = self._post(token='not-a-real-token', body={'section': 'prix', 'seconds': 5})
        self.assertEqual(resp.status_code, 404)

    def test_expired_token_returns_404(self):
        self.link.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.link.save()
        resp = self._post(body={'section': 'prix', 'seconds': 5})
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_isolation_by_token(self):
        other_company = _company('xsal16-other')
        other_client = Client.objects.create(
            company=other_company, nom='Autre', telephone='0600000099')
        other_devis = Devis.objects.create(
            company=other_company, reference='DEV-XSAL16-OTHER',
            client=other_client, statut=Devis.Statut.ENVOYE)
        other_link = ShareLink.for_devis(other_devis)

        self._post(body={'section': 'prix', 'seconds': 30})
        other_link.refresh_from_db()
        self.assertEqual(other_link.engagement or {}, {})

    def test_no_beacon_leaves_qj1_behaviour_unchanged(self):
        # Sans aucun appel engagement, Devis.engagement (serializer) reste
        # un dict vide — le comportement QJ1 (vues/consultation) est intact.
        self.assertEqual(self.link.engagement_summary, {})

    def test_deep_engagement_logs_chatter_note_once(self):
        self._post(body={'section': 'prix', 'seconds': 25})  # dépasse le seuil
        self.assertTrue(
            DevisActivity.objects.filter(
                devis=self.devis, kind=DevisActivity.Kind.NOTE).exists())
        count_after_first = DevisActivity.objects.filter(devis=self.devis).count()

        self._post(body={'section': 'etude', 'seconds': 25})  # déjà déclenché
        count_after_second = DevisActivity.objects.filter(devis=self.devis).count()
        self.assertEqual(count_after_first, count_after_second)

    def test_never_exposes_prix_achat_in_response(self):
        resp = self._post(body={'section': 'prix', 'seconds': 5})
        self.assertNotIn(b'prix_achat', resp.content)


class EngagementSerializerDisplayTests(TestCase):
    """XSAL16 — le devis affiche le résumé d'engagement par section côté
    vendeur (DevisSerializer.engagement)."""

    def setUp(self):
        cache.clear()
        self.company = _company('xsal16-disp-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Fassi', telephone='0611111111')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-XSAL16-DISP-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE)
        self.link = ShareLink.for_devis(self.devis)

    def test_serializer_reflects_engagement_summary(self):
        from apps.ventes.serializers import DevisSerializer
        self.link.engagement = {'prix': {'seconds': 120, 'hits': 4}}
        self.link.save()
        data = DevisSerializer(self.devis).data
        self.assertEqual(data['engagement']['prix']['seconds'], 120)
        self.assertEqual(data['engagement']['prix']['hits'], 4)

    def test_serializer_empty_without_beacon(self):
        from apps.ventes.serializers import DevisSerializer
        data = DevisSerializer(self.devis).data
        self.assertEqual(data['engagement'], {})
