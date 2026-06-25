"""AG4/AG5 — Tests des actions agentiques Ventes.

Couvre :
  - les actions du flux (créer le devis AUTO, éditer ses lignes / remise, PDF
    /proposal, accepter, convertir en BC, générer facture, enregistrer paiement)
    sont dans le catalogue AG1 ;
  - elles sont EXPOSÉES à un responsable/admin (qui porte les codes ERP de
    rattachement) et CACHÉES à un utilisateur en lecture seule ;
  - les niveaux de risque sont EXACTS (internal / outward / irreversible) — c'est
    ce qui pilote le garde-fou propose→confirm ;
  - ``company`` n'apparaît JAMAIS dans le schéma ``inputs`` (forcée serveur) ;
  - un devis créé via l'appel RELAYÉ (depuis un lead) force la société serveur ;
  - un paiement enregistré via l'endpoint relayé écrit un Paiement scopé société,
    avec isolation inter-tenant (on ne peut pas encaisser sur la facture d'une
    autre société).

Run :
    python manage.py test apps.ventes.tests.test_agent_actions -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import (
    Devis, Facture, LigneFacture, Paiement,
)
from apps.ventes.agent_actions import (
    CREER_AUTO,
    GENERER_PDF_DEVIS,
    ACCEPTER_DEVIS,
    CONVERTIR_EN_BON_COMMANDE,
    GENERER_FACTURE,
    ENREGISTRER_PAIEMENT,
    VENTES_ACTIONS,
    register_ventes_actions,
)
from apps.agent.registry import (
    all_actions, for_user, RISK_INTERNAL, RISK_OUTWARD, RISK_IRREVERSIBLE,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VentesAgentCatalogueTest(TestCase):
    """Les actions Ventes sont au catalogue et filtrées par permission ERP."""

    def setUp(self):
        register_ventes_actions()  # idempotent (ready() les pose déjà)
        self.company = Company.objects.create(nom='AG45 Co', slug='ag45-co')
        # Responsable : porte les trois codes de rattachement.
        self.resp_role = Role.objects.create(
            company=self.company, nom='Responsable Ventes',
            permissions=[
                'ventes_voir', 'ventes_creer', 'ventes_pdf', 'ventes_valider',
            ])
        self.resp = User.objects.create_user(
            username='ag45_resp', password='x', role=self.resp_role,
            company=self.company)
        # Lecture seule : ne porte que ventes_voir → ne voit aucune action.
        self.readonly_role = Role.objects.create(
            company=self.company, nom='Lecture', permissions=['ventes_voir'])
        self.readonly = User.objects.create_user(
            username='ag45_ro', password='x', role=self.readonly_role,
            company=self.company)

    def test_all_actions_registered(self):
        keys = {a.key for a in all_actions()}
        for action in VENTES_ACTIONS:
            self.assertIn(action.key, keys, action.key)

    def test_responsable_sees_all_quote_actions(self):
        keys = {a.key for a in for_user(self.resp)}
        for action in VENTES_ACTIONS:
            self.assertIn(action.key, keys, action.key)

    def test_readonly_user_sees_no_quote_actions(self):
        keys = {a.key for a in for_user(self.readonly)}
        for action in VENTES_ACTIONS:
            self.assertNotIn(action.key, keys, action.key)

    def test_required_permissions(self):
        self.assertEqual(CREER_AUTO.required_permission, 'ventes_creer')
        self.assertEqual(GENERER_PDF_DEVIS.required_permission, 'ventes_pdf')
        for action in (
            ACCEPTER_DEVIS, CONVERTIR_EN_BON_COMMANDE, GENERER_FACTURE,
            ENREGISTRER_PAIEMENT,
        ):
            self.assertEqual(
                action.required_permission, 'ventes_valider', action.key)

    def test_risk_levels_exact(self):
        # AG4
        self.assertEqual(CREER_AUTO.risk, RISK_INTERNAL)
        self.assertEqual(GENERER_PDF_DEVIS.risk, RISK_INTERNAL)
        self.assertEqual(ACCEPTER_DEVIS.risk, RISK_OUTWARD)
        # AG5
        self.assertEqual(CONVERTIR_EN_BON_COMMANDE.risk, RISK_OUTWARD)
        self.assertEqual(GENERER_FACTURE.risk, RISK_OUTWARD)
        self.assertEqual(ENREGISTRER_PAIEMENT.risk, RISK_IRREVERSIBLE)

    def test_inputs_never_include_company(self):
        for action in VENTES_ACTIONS:
            props = action.inputs.get('properties', {})
            self.assertNotIn('company', props, action.key)

    def test_creer_auto_accepts_lead(self):
        # Le client est résolu serveur depuis le lead → lead doit être un input.
        self.assertIn('lead', CREER_AUTO.inputs['properties'])

    def test_catalogue_endpoint_lists_actions_for_responsable(self):
        api = auth(self.resp)
        resp = api.get('/api/django/agent/actions/')
        self.assertEqual(resp.status_code, 200)
        keys = {a['key'] for a in resp.data['actions']}
        for action in VENTES_ACTIONS:
            self.assertIn(action.key, keys, action.key)

    def test_register_is_idempotent(self):
        before = len(all_actions())
        register_ventes_actions()
        register_ventes_actions()
        self.assertEqual(len(all_actions()), before)


class CreerAutoRelayedCallTest(TestCase):
    """Un devis créé via l'auto-devis relayé (depuis un lead) force la société et
    n'est JAMAIS vide quand le profil lead est dimensionnable."""

    def _seed_catalogue(self, company):
        def mk(nom, sku, prix):
            Produit.objects.create(
                company=company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)
        mk('Panneau Jinko 550W', f'PAN-{company.pk}', 1100)
        mk('Onduleur réseau Huawei 5kW Monophasé', f'ONDR-{company.pk}', 14000)

    def setUp(self):
        self.company = Company.objects.create(nom='AG45 Relay', slug='ag45-relay')
        self.other = Company.objects.create(nom='AG45 Other', slug='ag45-other')
        self.user = User.objects.create_user(
            username='ag45_relay', password='x', role_legacy='responsable',
            company=self.company)
        self._seed_catalogue(self.company)

    def test_auto_from_lead_forces_company_and_is_not_empty(self):
        lead = Lead.objects.create(
            company=self.company, nom='Relay', prenom='Lead',
            telephone='+212600000010', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        api = auth(self.user)
        resp = api.post(CREER_AUTO.endpoint, {
            'lead': lead.id,
            'taux_tva': '20.00',
            'remise_globale': '0',
            # Tentative d'injection : la société est ignorée côté serveur.
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        # Société forcée à celle du caller (jamais celle envoyée dans le corps).
        self.assertEqual(devis.company_id, self.company.id)
        # Client résolu serveur depuis le lead (sans doublon).
        self.assertEqual(devis.lead_id, lead.id)
        self.assertIsNotNone(devis.client_id)
        self.assertEqual(devis.client.company_id, self.company.id)
        # JAMAIS un devis vide : l'auto-devis a dimensionné des lignes.
        self.assertGreater(devis.lignes.count(), 0)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_auto_missing_data_returns_422_no_devis(self):
        lead = Lead.objects.create(
            company=self.company, nom='Vide', prenom='Lead')
        api = auth(self.user)
        resp = api.post(
            CREER_AUTO.endpoint, {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)


class EnregistrerPaiementRelayedCallTest(TestCase):
    """L'enregistrement d'un paiement écrit un Paiement scopé société + isole
    les tenants."""

    def _facture(self, company, client, total_ttc=Decimal('1200')):
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{MONTH}-{company.id}001',
            client=client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))
        produit = Produit.objects.create(
            company=company, nom='Panneau', sku=f'PV-{company.id}',
            prix_vente=Decimal('1000'), quantite_stock=100)
        facture = Facture.objects.create(
            company=company, reference=f'FAC-{MONTH}-{company.id}001',
            client=client, devis=devis, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return facture

    def setUp(self):
        self.company = Company.objects.create(nom='AG45 Pay', slug='ag45-pay')
        self.other = Company.objects.create(
            nom='AG45 PayOther', slug='ag45-pay-other')
        self.user = User.objects.create_user(
            username='ag45_pay', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Payeur', email='p@example.com',
            telephone='+212600000011', adresse='Casablanca')
        self.facture = self._facture(self.company, self.client_obj)

    def test_payment_writes_company_scoped_paiement(self):
        api = auth(self.user)
        endpoint = ENREGISTRER_PAIEMENT.endpoint.format(id=self.facture.id)
        resp = api.post(endpoint, {
            'montant': '300.00',
            'date_paiement': timezone.now().date().isoformat(),
            'mode': Paiement.Mode.VIREMENT,
            # Injection : la société est ignorée côté serveur.
            'company': self.other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = Paiement.objects.get(facture=self.facture)
        # Société forcée = celle de la facture (jamais celle du corps).
        self.assertEqual(paiement.company_id, self.company.id)
        self.assertEqual(paiement.montant, Decimal('300.00'))
        self.assertEqual(paiement.created_by_id, self.user.id)

    def test_zero_amount_rejected(self):
        api = auth(self.user)
        endpoint = ENREGISTRER_PAIEMENT.endpoint.format(id=self.facture.id)
        resp = api.post(endpoint, {
            'montant': '0',
            'date_paiement': timezone.now().date().isoformat(),
            'mode': Paiement.Mode.ESPECES,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Paiement.objects.filter(facture=self.facture).exists())

    def test_cross_tenant_payment_blocked(self):
        # Une facture d'une AUTRE société est invisible (404) — pas d'encaissement
        # cross-tenant possible via l'endpoint relayé.
        other_client = Client.objects.create(
            company=self.other, nom='Autre', email='o@example.com',
            telephone='+212600000012', adresse='Rabat')
        foreign_facture = self._facture(self.other, other_client)
        api = auth(self.user)
        endpoint = ENREGISTRER_PAIEMENT.endpoint.format(id=foreign_facture.id)
        resp = api.post(endpoint, {
            'montant': '100.00',
            'date_paiement': timezone.now().date().isoformat(),
            'mode': Paiement.Mode.ESPECES,
        }, format='json')
        self.assertEqual(resp.status_code, 404, getattr(resp, 'data', resp))
        self.assertFalse(
            Paiement.objects.filter(facture=foreign_facture).exists())
