"""Tests FG44 — refus explicite d'un devis (date + motif + chatter + lead perdu)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, DevisActivity

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='rfus-co', nom='Refus Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisRefus(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='rfus_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Refus',
            email='rfus@example.com', telephone='+212600000099')

    def _devis(self, num=1, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-R{num:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_refuser_sets_statut_and_fields(self):
        """POST /refuser/ → statut=refuse, date_refus, motif_refus renseignés."""
        devis = self._devis(num=1)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {'motif': 'Prix trop élevé', 'date': '2026-06-15'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'refuse')
        self.assertEqual(str(devis.date_refus), '2026-06-15')
        self.assertEqual(devis.motif_refus, 'Prix trop élevé')

    def test_refuser_default_date_today(self):
        """Sans date explicite, date_refus = aujourd'hui."""
        devis = self._devis(num=2)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.date_refus, timezone.now().date())

    def test_refuser_logs_chatter(self):
        """Le refus est consigné dans le chatter du devis (DevisActivity)."""
        devis = self._devis(num=3)
        self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {'motif': 'Concurrent moins cher', 'date': '2026-06-15'},
            format='json')
        acts = DevisActivity.objects.filter(devis=devis)
        self.assertEqual(acts.count(), 1)
        self.assertIn('Concurrent', acts.first().body)
        self.assertIn('2026-06-15', acts.first().body)

    def test_refuser_brouillon_allowed(self):
        """Un devis brouillon peut aussi être refusé."""
        devis = self._devis(num=4, statut=Devis.Statut.BROUILLON)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'refuse')

    # ── Statut guard ─────────────────────────────────────────────────────────

    def test_refuser_already_accepted_rejected(self):
        """Un devis déjà accepté ne peut pas être refusé (409)."""
        devis = self._devis(num=5, statut=Devis.Statut.ACCEPTE)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')

    def test_refuser_already_refused_rejected(self):
        """Un devis déjà refusé ne peut pas l'être à nouveau (409)."""
        devis = self._devis(num=6, statut=Devis.Statut.REFUSE)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)

    def test_refuser_expired_rejected(self):
        """Un devis expiré ne peut pas être refusé (409)."""
        devis = self._devis(num=7, statut=Devis.Statut.EXPIRE)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)

    def test_refuser_invalid_date_rejected(self):
        """Date invalide → 400, statut inchangé."""
        devis = self._devis(num=8)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {'date': 'pas-une-date'}, format='json')
        self.assertEqual(r.status_code, 400)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'refuse')

    # ── Company scoping ───────────────────────────────────────────────────────

    def test_refuser_cross_company_forbidden(self):
        """Un devis d'une autre société est inaccessible (404)."""
        other_company, _ = Company.objects.get_or_create(
            slug='other-rfus-co', defaults={'nom': 'Other Rfus Co'})
        other_client = Client.objects.create(
            company=other_company, nom='Other', email='other@ex.com',
            telephone='+212600000098')
        other_devis = Devis.objects.create(
            company=other_company,
            reference=f'DEV-{MONTH}-X0001',
            client=other_client, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        r = self.api.post(
            f'/api/django/ventes/devis/{other_devis.id}/refuser/',
            {}, format='json')
        self.assertEqual(r.status_code, 404, r.data)

    # ── Lead perdu sync via event bus ─────────────────────────────────────────

    def test_refuser_with_marquer_lead_perdu_marks_lead(self):
        """FG44 — marquer_lead_perdu=true → lead.perdu=True + motif_perte."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Rfus', stage='QUOTE_SENT')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-R0010',
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {'motif': 'Budget insuffisant', 'marquer_lead_perdu': True},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertTrue(lead.perdu)
        self.assertEqual(lead.motif_perte, 'Budget insuffisant')

    def test_refuser_without_marquer_lead_perdu_keeps_lead_intact(self):
        """Sans marquer_lead_perdu, le lead reste intact."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Rfus2', stage='QUOTE_SENT')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-R0011',
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {'motif': 'Autre projet'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertFalse(lead.perdu)

    def test_refuser_historique_accessible(self):
        """Après refus, l'historique du devis expose l'activité de refus."""
        devis = self._devis(num=12)
        self.api.post(
            f'/api/django/ventes/devis/{devis.id}/refuser/',
            {'motif': 'Test historique', 'date': '2026-06-20'}, format='json')
        h = self.api.get(f'/api/django/ventes/devis/{devis.id}/historique/')
        self.assertEqual(h.status_code, 200)
        bodies = [a['body'] for a in h.data]
        self.assertTrue(any('Test historique' in (b or '') for b in bodies))
