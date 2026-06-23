"""U12 — lien DIRECT vers le lead d'origine sur Facture & BonCommande.

Le lead est snapshoté à la création depuis le devis source (devis.lead, ou
bon_commande.devis.lead pour la chaîne BC → facture), de sorte que « tous les
documents d'un lead » soient directement interrogeables sans traverser le devis
(qui peut passer à NULL si le devis est supprimé).

Couvre : le FK est posé à la création par les trois voies (échéancier
devis → facture, chaîne BC → facture, conversion devis → BC), la robustesse à
la suppression du devis (le lien direct survit), le scoping société, et le
no-op pour les documents sans devis/lead source.

Run :
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_lead_direct_fk -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import (
    Devis, LigneDevis, BonCommande, Facture,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='leadfk-co', nom='LeadFK Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='leadfk@example.com'):
    return Client.objects.create(
        company=company, nom='LeadFK', prenom='Client',
        email=email, telephone='+212600000010', adresse='Casablanca',
    )


def make_lead(company, nom='LeadFK Lead'):
    return Lead.objects.create(company=company, nom=nom)


def make_accepted_devis(company, client, lead=None, ref_suffix='8001',
                        mode='residentiel'):
    """Devis ACCEPTÉ à 17 000 TTC (15 000 HT + 2 000 TVA, split 10/20)."""
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{MONTH}-{ref_suffix}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
        mode_installation=mode,
    )
    panneau = Produit.objects.create(
        company=company, nom='Panneau PV 450W', sku=f'PV-450-{ref_suffix}',
        prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('10.00'),
    )
    onduleur = Produit.objects.create(
        company=company, nom='Onduleur 5kW', sku=f'OND-5-{ref_suffix}',
        prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'),
    )
    LigneDevis.objects.create(
        devis=devis, produit=panneau, designation='Panneau PV 450W',
        quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
        remise=Decimal('0'), taux_tva=Decimal('10.00'),
    )
    LigneDevis.objects.create(
        devis=devis, produit=onduleur, designation='Onduleur 5kW',
        quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
        remise=Decimal('0'), taux_tva=Decimal('20.00'),
    )
    return devis


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestLeadSnapshotOnCreation(TestCase):
    """Le FK lead est posé à la création depuis le devis source (model.save)."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.lead = make_lead(self.company)

    def test_facture_echeancier_snapshots_lead_from_devis(self):
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8001')
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8001',
            devis=devis, client=self.client_obj,
        )
        self.assertEqual(facture.lead_id, self.lead.id)

    def test_facture_from_bc_chain_snapshots_lead(self):
        """Chaîne BC → facture : la facture porte `bon_commande`, pas `devis` ;
        le lead vient quand même de bon_commande.devis.lead."""
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8002')
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-8002',
            devis=devis, client=self.client_obj,
        )
        self.assertEqual(bc.lead_id, self.lead.id)
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8002',
            bon_commande=bc, client=self.client_obj,
        )
        self.assertEqual(facture.lead_id, self.lead.id)

    def test_bon_commande_snapshots_lead_from_devis(self):
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8003')
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-8003',
            devis=devis, client=self.client_obj,
        )
        self.assertEqual(bc.lead_id, self.lead.id)

    def test_no_lead_when_devis_has_no_lead(self):
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=None, ref_suffix='8004')
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8004',
            devis=devis, client=self.client_obj,
        )
        self.assertIsNone(facture.lead_id)

    def test_no_lead_for_document_without_source_devis(self):
        """Facture sans devis ni BC (ex. contrat de maintenance) : lead reste NULL."""
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8005',
            client=self.client_obj, libelle='Maintenance',
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'),
        )
        self.assertIsNone(facture.lead_id)

    def test_explicit_lead_is_not_overwritten(self):
        """Un lead déjà posé n'est jamais écrasé par le snapshot."""
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8006')
        other_lead = make_lead(self.company, nom='Autre lead')
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8006',
            devis=devis, client=self.client_obj, lead=other_lead,
        )
        self.assertEqual(facture.lead_id, other_lead.id)


class TestLeadFKSurvivesDevisDeletion(TestCase):
    """La motivation U12 : le lien direct survit à la suppression du devis."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.lead = make_lead(self.company)

    def test_facture_keeps_lead_after_devis_deleted(self):
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8101')
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8101',
            devis=devis, client=self.client_obj,
        )
        devis.delete()
        facture.refresh_from_db()
        # devis FK passe à NULL (SET_NULL) mais le lien direct lead survit.
        self.assertIsNone(facture.devis_id)
        self.assertEqual(facture.lead_id, self.lead.id)

    def test_lead_scoped_query_uses_direct_fk(self):
        """Toutes les factures d'un lead sont interrogeables via le FK direct."""
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8102')
        f1 = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8102',
            devis=devis, client=self.client_obj,
        )
        devis.delete()
        factures = list(Facture.objects.filter(lead=self.lead))
        self.assertEqual(factures, [f1])


class TestLeadFKCompanyScoping(TestCase):
    """Multi-tenant : le lead snapshoté reste celui du devis de la société."""

    def test_lead_belongs_to_same_company_as_document(self):
        co_a = make_company(slug='leadfk-a', nom='A')
        client_a = make_client(co_a, email='a@example.com')
        lead_a = make_lead(co_a, nom='Lead A')
        devis = make_accepted_devis(
            co_a, client_a, lead=lead_a, ref_suffix='8201')
        facture = Facture.objects.create(
            company=co_a, reference=f'FAC-{MONTH}-8201',
            devis=devis, client=client_a,
        )
        self.assertEqual(facture.lead.company_id, co_a.id)
        self.assertEqual(facture.company_id, facture.lead.company_id)

    def test_other_company_lead_query_is_isolated(self):
        co_a = make_company(slug='leadfk-a2', nom='A2')
        co_b = make_company(slug='leadfk-b2', nom='B2')
        client_a = make_client(co_a, email='a2@example.com')
        lead_a = make_lead(co_a, nom='Lead A2')
        lead_b = make_lead(co_b, nom='Lead B2')
        devis = make_accepted_devis(
            co_a, client_a, lead=lead_a, ref_suffix='8202')
        Facture.objects.create(
            company=co_a, reference=f'FAC-{MONTH}-8202',
            devis=devis, client=client_a,
        )
        # Le lead d'une autre société n'attrape aucune facture.
        self.assertEqual(
            Facture.objects.filter(lead=lead_b).count(), 0)
        self.assertEqual(
            Facture.objects.filter(lead=lead_a).count(), 1)


class TestLeadFKThroughApi(TestCase):
    """Les vraies voies de création API posent le FK lead."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.lead = make_lead(self.company)
        self.resp = User.objects.create_user(
            username='leadfk_resp', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.api = auth(self.resp)

    def test_convertir_bc_sets_lead(self):
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8301')
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/convertir-bc/')
        self.assertEqual(r.status_code, 201, r.data)
        bc = BonCommande.objects.get(devis=devis)
        self.assertEqual(bc.lead_id, self.lead.id)

    def test_generer_facture_tranche_sets_lead(self):
        devis = make_accepted_devis(
            self.company, self.client_obj, lead=self.lead, ref_suffix='8302')
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(reference=r.data['reference'])
        self.assertEqual(facture.lead_id, self.lead.id)
