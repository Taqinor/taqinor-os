"""XFAC29 — Facturation électronique DGI SORTANTE : couche de transmission
(signature + envoi à une plateforme agréée), key-gated OFF par défaut.

Couvre :
  * `dgi_transmission_actif` OFF (défaut) : endpoint 404, `dgi_statut` reste
    à sa valeur par défaut ('a_transmettre'), aucun champ modifié.
  * Provider mock ON : transmission réussie → statut 'acceptee' + référence
    posée ; jamais deux transmissions (idempotence : re-transmettre une
    facture déjà acceptée renvoie le même état sans changer la référence).
  * Provider NoOp explicite ON (aucune config réelle) : transmission refusée
    proprement → statut 'rejetee' + motif de rejet, sans exception, sans
    appel réseau.
  * Un rejet peut être rejoué (nouvelle tentative change le statut si le
    provider est ensuite basculé sur mock).
  * Isolation multi-tenant : transmettre la facture d'une autre société 404.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.dgi.transmission import (
    is_dgi_transmission_enabled, transmettre_facture,
    get_transmission_provider, MockDgiTransmissionProvider,
    NoOpDgiTransmissionProvider,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xfac29TestBase(TestCase):
    def setUp(self):
        self.company = make_company('xfac29-co', 'XFAC29 Co')
        self.user = User.objects.create_user(
            username='xfac29_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.profile = CompanyProfile.get(company=self.company)
        self.profile.nom = 'Vendeur SARL'
        self.profile.ice = 'ICE-SELLER-XFAC29'
        self.profile.identifiant_fiscal = 'IF-XFAC29'
        self.profile.rc = 'RC-XFAC29'
        self.profile.save()
        self.client_b2b = Client.objects.create(
            company=self.company, nom='Acme29', prenom='Pro',
            email='pro29@acme.ma', telephone='+212600000029', adresse='Casa',
            type_client='entreprise', ice='ICE-CLIENT-XFAC29')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau29', sku='XFAC29-PV-1',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=50, tva=Decimal('20.00'))

    def _facture(self):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-XFAC29',
            client=self.client_b2b, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            conditions_paiement='Virement à 30 jours')
        LigneFacture.objects.create(
            facture=facture, produit=self.produit,
            designation='Panneau PV 550W', quantite=Decimal('2'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return facture


class TestToggleOffByDefault(Xfac29TestBase):
    def test_toggle_defaults_off(self):
        fresh = make_company('xfac29-fresh', 'Fresh29 Co')
        prof = CompanyProfile.get(company=fresh)
        self.assertFalse(prof.dgi_transmission_actif)
        self.assertEqual(prof.dgi_transmission_provider, 'noop')
        self.assertFalse(is_dgi_transmission_enabled(fresh))

    def test_endpoint_404_when_off(self):
        facture = self._facture()
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/dgi-transmettre/')
        self.assertEqual(r.status_code, 404)

    def test_no_field_change_when_off(self):
        facture = self._facture()
        result = transmettre_facture(facture)
        facture.refresh_from_db()
        self.assertEqual(result.dgi_statut, Facture.DgiStatut.A_TRANSMETTRE)
        self.assertEqual(facture.dgi_statut, Facture.DgiStatut.A_TRANSMETTRE)
        self.assertEqual(facture.dgi_reference, '')


class TestNoOpProviderExplicit(Xfac29TestBase):
    """ON mais sans config réelle (provider noop explicite) → échec propre."""

    def test_noop_rejects_cleanly_no_network(self):
        self.profile.dgi_transmission_actif = True
        self.profile.dgi_transmission_provider = 'noop'
        self.profile.save()
        facture = self._facture()

        result = transmettre_facture(facture)

        self.assertEqual(result.dgi_statut, Facture.DgiStatut.REJETEE)
        self.assertEqual(result.dgi_reference, '')
        self.assertTrue(result.dgi_motif_rejet)

    def test_provider_registry_default_is_noop(self):
        provider = get_transmission_provider('unknown-key')
        self.assertIsInstance(provider, NoOpDgiTransmissionProvider)


class TestMockProviderTransmission(Xfac29TestBase):
    """ON avec le provider mock (tests) → transmission simulée réussie."""

    def setUp(self):
        super().setUp()
        self.profile.dgi_transmission_actif = True
        self.profile.dgi_transmission_provider = 'mock'
        self.profile.save()

    def test_mock_transmission_succeeds_via_service(self):
        facture = self._facture()
        result = transmettre_facture(facture)

        self.assertEqual(result.dgi_statut, Facture.DgiStatut.ACCEPTEE)
        self.assertTrue(result.dgi_reference.startswith('DGI-MOCK-'))
        self.assertEqual(result.dgi_motif_rejet, '')

    def test_mock_transmission_via_endpoint(self):
        facture = self._facture()
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/dgi-transmettre/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['dgi_statut'], 'acceptee')
        self.assertTrue(r.data['dgi_reference'])
        facture.refresh_from_db()
        self.assertEqual(facture.dgi_statut, Facture.DgiStatut.ACCEPTEE)

    def test_never_two_transmissions_for_same_facture(self):
        facture = self._facture()
        first = transmettre_facture(facture)
        first_ref = first.dgi_reference
        self.assertEqual(first.dgi_statut, Facture.DgiStatut.ACCEPTEE)

        # Re-transmettre une facture déjà ACCEPTÉE ne doit rien changer.
        second = transmettre_facture(first)
        self.assertEqual(second.dgi_statut, Facture.DgiStatut.ACCEPTEE)
        self.assertEqual(second.dgi_reference, first_ref)

    def test_rejected_transmission_can_be_replayed(self):
        # D'abord rejetée (noop), puis basculée sur mock → rejouable.
        self.profile.dgi_transmission_provider = 'noop'
        self.profile.save()
        facture = self._facture()
        rejected = transmettre_facture(facture)
        self.assertEqual(rejected.dgi_statut, Facture.DgiStatut.REJETEE)

        self.profile.dgi_transmission_provider = 'mock'
        self.profile.save()
        replayed = transmettre_facture(rejected)
        self.assertEqual(replayed.dgi_statut, Facture.DgiStatut.ACCEPTEE)
        self.assertTrue(replayed.dgi_reference)

    def test_cross_tenant_isolation_404(self):
        other_company = make_company('xfac29-other', 'Other29 Co')
        other_user = User.objects.create_user(
            username='xfac29_other', password='x', role_legacy='responsable',
            company=other_company)
        other_api = auth(other_user)
        facture = self._facture()
        r = other_api.post(
            f'/api/django/ventes/factures/{facture.id}/dgi-transmettre/')
        self.assertEqual(r.status_code, 404)


class TestMockProviderDirect(TestCase):
    """Le provider mock lui-même, indépendamment du service haut niveau."""

    def test_mock_provider_returns_ok_with_reference(self):
        provider = MockDgiTransmissionProvider()
        result = provider.sign_and_transmit(None, '<xml/>')
        self.assertTrue(result['ok'])
        self.assertTrue(result['reference'])
        self.assertEqual(result['motif_rejet'], '')
