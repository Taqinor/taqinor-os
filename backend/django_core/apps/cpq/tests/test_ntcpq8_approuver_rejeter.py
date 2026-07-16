"""NTCPQ8 — approuver-etape / rejeter-etape + chatter + déblocage envoi."""
from decimal import Decimal

from django.test import TestCase

from apps.cpq.models import RegleApprobationRemise, EtapeApprobationDevis
from apps.cpq import services
from apps.ventes.models import DevisActivity
from apps.ventes.services import mark_devis_sent
from testkit.factories import CompanyFactory, DevisFactory, UserFactory


class TestApprouverRejeter(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company)
        RegleApprobationRemise.objects.create(
            company=self.company, remise_min_pct=Decimal('20'),
            remise_max_pct=Decimal('100'), nombre_approbateurs=2)
        self.devis = DevisFactory(
            company=self.company, remise_globale=Decimal('25'))
        services.lancer_approbation_devis(self.devis)

    def test_approuver_toutes_les_etapes_debloque_envoi(self):
        etape1, toutes1 = services.approuver_etape_devis(
            self.devis, user=self.user)
        self.assertFalse(toutes1)  # il reste l'étape 2
        etape2, toutes2 = services.approuver_etape_devis(
            self.devis, user=self.user)
        self.assertTrue(toutes2)
        mark_devis_sent(devis=self.devis)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')

    def test_rejeter_remet_en_brouillon_et_logue(self):
        # simulate the devis moved to envoye is prevented; force a non-brouillon
        # state to prove reject resets it.
        self.devis.statut = 'envoye'
        self.devis.save()
        etape = services.rejeter_etape_devis(
            self.devis, user=self.user, motif='Remise trop élevée')
        self.assertEqual(etape.statut, EtapeApprobationDevis.Statut.REJETE)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')
        # chatter : une entrée avec l'auteur et le motif.
        act = DevisActivity.objects.filter(
            devis=self.devis).order_by('-created_at').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.user_id, self.user.id)
        self.assertIn('Remise trop élevée', act.body)

    def test_endpoint_approuver_etape(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        # user needs responsable/admin role for the action
        staff = UserFactory(
            company=self.company, role_legacy='responsable')
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(staff)}')
        resp = client.post(
            f'/api/django/ventes/devis/{self.devis.id}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.json()['toutes_approuvees'])
