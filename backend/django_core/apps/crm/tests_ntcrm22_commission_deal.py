"""NTCRM22 — Commission apporteur calculée automatiquement à l'acceptation
du devis lié à un DealEnregistre APPROUVE."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Apporteur, DealEnregistre, Lead
from apps.crm.services import resolve_client_for_lead
from apps.roles.models import Role
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()


class CommissionDealTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM22', slug='taqinor-ntcrm22')
        self.apporteur = Apporteur.objects.create(
            company=self.company, nom='Apporteur commission',
            taux_commission_pct=Decimal('5.00'))
        self.lead = Lead.objects.create(company=self.company, nom='Lead deal')
        self.deal = DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur, lead=self.lead,
            statut=DealEnregistre.Statut.APPROUVE)
        self.client_obj = resolve_client_for_lead(self.lead)
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_obj, lead=self.lead,
            reference='DVC1', statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=self.devis, designation='Panneau', quantite=1,
            prix_unitaire=Decimal('10000.00'))

    def test_commission_calculee_et_statut_a_payer(self):
        devis_accepted.send(
            sender='test', devis=self.devis, user=None, ancien_statut='envoye')
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.statut, DealEnregistre.Statut.A_PAYER)
        self.assertEqual(self.deal.montant_commission_du, Decimal('500.00'))

    def test_deal_non_approuve_ignore(self):
        self.deal.statut = DealEnregistre.Statut.EN_ATTENTE
        self.deal.save(update_fields=['statut'])
        devis_accepted.send(
            sender='test', devis=self.devis, user=None, ancien_statut='envoye')
        self.deal.refresh_from_db()
        self.assertIsNone(self.deal.montant_commission_du)

    def test_sans_taux_commission_ignore(self):
        self.apporteur.taux_commission_pct = None
        self.apporteur.save(update_fields=['taux_commission_pct'])
        devis_accepted.send(
            sender='test', devis=self.devis, user=None, ancien_statut='envoye')
        self.deal.refresh_from_db()
        self.assertIsNone(self.deal.montant_commission_du)


class APayerEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM22b', slug='taqinor-ntcrm22b')
        self.role = Role.objects.create(
            company=self.company, nom='Comptable', permissions=['crm_creer'])
        self.user = User.objects.create_user(
            username='compta_ntcrm22', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_liste_seulement_les_a_payer(self):
        apporteur = Apporteur.objects.create(company=self.company, nom='A')
        lead1 = Lead.objects.create(company=self.company, nom='L1')
        lead2 = Lead.objects.create(company=self.company, nom='L2')
        DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur, lead=lead1,
            statut=DealEnregistre.Statut.A_PAYER,
            montant_commission_du=Decimal('300.00'))
        DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur, lead=lead2,
            statut=DealEnregistre.Statut.EN_ATTENTE)

        resp = self.api.get('/api/django/crm/deals-enregistres/a-payer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['statut'], 'a_payer')
