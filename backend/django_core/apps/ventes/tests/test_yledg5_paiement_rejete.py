"""Tests YLEDG5 — chemin d'exception « paiement rejeté » (chèque impayé /
virement rejeté). Rejeter un paiement rouvre la facture (montant_du remonte),
le rejet est visible et infalsifiable (jamais de suppression), double rejet
refusé (409), scoping multi-tenant, émission de paiement_rejete."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from core.events import paiement_rejete

User = get_user_model()


def make_company(slug='yledg5-co', nom='YLEDG5 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestPaiementRejete(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='yledg5_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L5',
            email='yledg5@example.com', telephone='+212600000008')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG5',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG5-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))
        # Encaisse intégralement -> facture payée.
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            f'enregistrer-paiement/',
            {'montant': '6000', 'date_paiement': date.today().isoformat(),
             'mode': 'cheque'}, format='json')
        assert r.status_code == 201, r.data
        self.facture.refresh_from_db()
        assert self.facture.statut == Facture.Statut.PAYEE
        self.paiement = self.facture.paiements.get()

    def test_rejeter_reopens_facture(self):
        r = self.api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/rejeter/',
            {'motif': 'Chèque impayé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut, Paiement.Statut.REJETE)
        self.assertEqual(self.paiement.motif_rejet, 'Chèque impayé')
        self.assertEqual(self.facture.montant_du, Decimal('6000'))
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)
        # Never deleted — audit trail preserved.
        self.assertTrue(
            Paiement.objects.filter(pk=self.paiement.pk).exists())

    def test_rejeter_sets_en_retard_if_past_due(self):
        Facture.objects.filter(pk=self.facture.pk).update(
            date_echeance=date.today() - timedelta(days=10))
        r = self.api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/rejeter/',
            {'motif': 'Virement rejeté'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.EN_RETARD)

    def test_rejeter_without_motif_rejected(self):
        r = self.api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/rejeter/',
            {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut, Paiement.Statut.ENCAISSE)

    def test_double_rejet_refused(self):
        r1 = self.api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/rejeter/',
            {'motif': 'Chèque impayé'}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = self.api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/rejeter/',
            {'motif': 'Encore'}, format='json')
        self.assertEqual(r2.status_code, 409, r2.data)

    def test_paiement_rejete_event_emitted(self):
        received = []

        def _listener(sender, paiement, facture, montant, company, **kwargs):
            received.append((paiement.id, facture.id, montant, company.id))
        paiement_rejete.connect(
            _listener, dispatch_uid='test_yledg5_listener')
        try:
            r = self.api.post(
                f'/api/django/ventes/paiements/{self.paiement.id}/rejeter/',
                {'motif': 'Chèque impayé'}, format='json')
            self.assertEqual(r.status_code, 200, r.data)
        finally:
            paiement_rejete.disconnect(dispatch_uid='test_yledg5_listener')
        self.assertEqual(len(received), 1)
        pid, fid, montant, cid = received[0]
        self.assertEqual(pid, self.paiement.id)
        self.assertEqual(fid, self.facture.id)
        self.assertEqual(montant, Decimal('6000'))
        self.assertEqual(cid, self.company.id)

    def test_cross_company_rejeter_404(self):
        other = make_company(slug='yledg5-co2', nom='YLEDG5 Co2')
        other_user = User.objects.create_user(
            username='yledg5_other', password='x', role_legacy='responsable',
            company=other)
        other_api = auth(other_user)
        r = other_api.post(
            f'/api/django/ventes/paiements/{self.paiement.id}/rejeter/',
            {'motif': 'x'}, format='json')
        self.assertEqual(r.status_code, 404)
