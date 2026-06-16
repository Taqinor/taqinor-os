"""Tests N9/N11/N30 — acceptation devis « Bon pour accord », conformité
Article 145 CGI (mentions manquantes), date de livraison par défaut depuis la
mise en service du chantier, et détection des trous de numérotation.

Run :
    python manage.py test apps.ventes.tests.test_conformite -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
from apps.ventes.utils.references import detect_reference_gaps

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='conf-co', nom='Conf Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='conf@example.com', **extra):
    return Client.objects.create(
        company=company, nom='Conf', prenom='Client',
        email=email, telephone='+212600000010', adresse='Casablanca', **extra)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_devis(company, client_obj, statut=Devis.Statut.ENVOYE, ref=None,
               lead=None):
    devis = Devis.objects.create(
        company=company, reference=ref or f'DEV-{MONTH}-7001',
        client=client_obj, statut=statut, taux_tva=Decimal('20.00'),
        mode_installation='residentiel', lead=lead,
    )
    prod = Produit.objects.create(
        company=company, nom=f'Onduleur {ref or "X"}', sku=f'OND-{ref or "X"}',
        prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
    LigneDevis.objects.create(
        devis=devis, produit=prod, designation='Onduleur 5kW',
        quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
        remise=Decimal('0'), taux_tva=Decimal('20.00'))
    return devis


class TestDevisAcceptance(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.user = User.objects.create_user(
            username='conf_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_accepter_sets_fields_status_and_flag(self):
        devis = make_devis(self.company, self.client_obj)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Alaoui', 'date': '2026-06-15'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(devis.accepte_par_nom, 'M. Alaoui')
        self.assertEqual(devis.date_acceptation, date(2026, 6, 15))
        self.assertTrue(devis.bon_pour_accord)
        self.assertEqual(devis.accepte_par_user_id, self.user.id)

    def test_accepter_requires_name(self):
        devis = make_devis(self.company, self.client_obj)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'date': '2026-06-15'}, format='json')
        self.assertEqual(r.status_code, 400)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_accepter_defaults_date_to_today(self):
        devis = make_devis(self.company, self.client_obj)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.date_acceptation, timezone.now().date())

    def test_accepter_logs_to_lead_chatter(self):
        from apps.crm.models import Lead, LeadActivity
        lead = Lead.objects.create(company=self.company, nom='Prospect')
        devis = make_devis(self.company, self.client_obj, lead=lead)
        before = LeadActivity.objects.filter(lead=lead).count()
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Mme Bennani', 'date': '2026-06-15'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertEqual(notes.count(), before + 1)
        self.assertIn('Bon pour accord', notes.first().body)
        self.assertIn('Mme Bennani', notes.first().body)

    def test_acceptance_enables_chantier_creation(self):
        """L'acceptation explicite (statut accepte) débloque le chantier."""
        devis = make_devis(self.company, self.client_obj)
        # Avant acceptation : la création du chantier est refusée.
        r0 = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r0.status_code, 400, r0.data)
        # On accepte, puis la création du chantier passe.
        self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-15'}, format='json')
        r1 = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertIn(r1.status_code, (200, 201), r1.data)

    def test_company_scoping_other_company_404(self):
        other = make_company(slug='other-co', nom='Other')
        other_client = make_client(other, email='o@example.com')
        devis = make_devis(other, other_client, ref=f'DEV-{MONTH}-7099')
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'X', 'date': '2026-06-15'}, format='json')
        self.assertEqual(r.status_code, 404)


class TestFactureConformite(TestCase):
    def setUp(self):
        self.company = make_company(slug='conf-fac-co', nom='Conf Fac Co')
        self.user = User.objects.create_user(
            username='conf_fac_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def _make_facture(self, client_obj, **kw):
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-7001',
            client=client_obj, statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), **kw)
        prod = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PVF-1',
            prix_vente=Decimal('1000'), quantite_stock=50, tva=Decimal('10.00'))
        LigneFacture.objects.create(
            facture=facture, produit=prod, designation='Panneau PV',
            quantite=Decimal('5'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('10.00'))
        return facture

    def test_b2b_facture_missing_client_ice_warns(self):
        """Client professionnel (Entreprise) sans ICE → mention manquante."""
        client_pro = make_client(
            self.company, email='pro@example.com', type_client='entreprise')
        facture = self._make_facture(client_pro)
        manquantes = facture.mentions_manquantes
        self.assertIn('ICE du client (client professionnel)', manquantes)
        # Une mention manquante NE bloque PAS l'émission.
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_b2c_facture_does_not_require_client_ice(self):
        client_part = make_client(
            self.company, email='part@example.com', type_client='particulier')
        facture = self._make_facture(client_part)
        self.assertNotIn(
            'ICE du client (client professionnel)',
            facture.mentions_manquantes)

    def test_missing_delivery_date_and_payment_terms_warn(self):
        client_obj = make_client(self.company, email='c@example.com')
        facture = self._make_facture(client_obj)
        manquantes = facture.mentions_manquantes
        self.assertIn('Date de livraison / prestation', manquantes)
        self.assertIn('Conditions et mode de paiement', manquantes)

    def test_conformity_exposed_on_serializer(self):
        client_obj = make_client(self.company, email='c2@example.com')
        facture = self._make_facture(client_obj)
        r = self.api.get(f'/api/django/ventes/factures/{facture.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('mentions_manquantes', r.data)
        self.assertIsInstance(r.data['mentions_manquantes'], list)

    def test_complete_facture_has_no_missing_mentions(self):
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=self.company)
        profile.nom = 'Conf Fac Co'
        profile.identifiant_fiscal = 'IF123'
        profile.ice = 'ICE000111222'
        profile.rc = 'RC456'
        profile.save()
        client_obj = make_client(self.company, email='full@example.com')
        facture = self._make_facture(
            client_obj, date_livraison=date(2026, 6, 1),
            conditions_paiement='Virement à 30 jours')
        self.assertEqual(facture.mentions_manquantes, [])


class TestFactureDateLivraisonDefault(TestCase):
    def setUp(self):
        self.company = make_company(slug='conf-mes-co', nom='Conf MES Co')
        self.client_obj = make_client(self.company, email='mes@example.com')
        self.user = User.objects.create_user(
            username='conf_mes_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_date_livraison_defaults_from_chantier_mes(self):
        from apps.installations.models import Installation
        devis = make_devis(
            self.company, self.client_obj, statut=Devis.Statut.ACCEPTE,
            ref=f'DEV-{MONTH}-7500')
        Installation.objects.create(
            company=self.company, reference=f'CH-{MONTH}-1', client=self.client_obj,
            devis=devis, date_mise_en_service=date(2026, 6, 10))
        # Génère la première tranche (acompte) → date_livraison = MES.
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(id=r.data['id'])
        self.assertEqual(facture.date_livraison, date(2026, 6, 10))

    def test_date_livraison_none_without_chantier(self):
        devis = make_devis(
            self.company, self.client_obj, statut=Devis.Statut.ACCEPTE,
            ref=f'DEV-{MONTH}-7501')
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(id=r.data['id'])
        self.assertIsNone(facture.date_livraison)


class TestNumberingGaps(TestCase):
    def setUp(self):
        self.company = make_company(slug='conf-gap-co', nom='Conf Gap Co')
        self.client_obj = make_client(self.company, email='gap@example.com')
        self.admin = User.objects.create_user(
            username='conf_gap_admin', password='x', role_legacy='admin',
            company=self.company)
        self.resp = User.objects.create_user(
            username='conf_gap_resp', password='x', role_legacy='responsable',
            company=self.company)

    def _facture(self, ref):
        return Facture.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'))

    def test_detect_gap_in_sequence(self):
        self._facture(f'FAC-{MONTH}-0001')
        self._facture(f'FAC-{MONTH}-0002')
        self._facture(f'FAC-{MONTH}-0004')  # trou : 0003 manquant
        gaps = detect_reference_gaps(Facture, 'FAC', self.company)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]['missing'], [3])
        self.assertEqual(gaps[0]['expected_max'], 4)

    def test_no_gap_when_sequence_contiguous(self):
        self._facture(f'FAC-{MONTH}-0001')
        self._facture(f'FAC-{MONTH}-0002')
        self.assertEqual(detect_reference_gaps(Facture, 'FAC', self.company), [])

    def test_endpoint_admin_only(self):
        self._facture(f'FAC-{MONTH}-0001')
        self._facture(f'FAC-{MONTH}-0003')
        api_admin = auth(self.admin)
        r = api_admin.get('/api/django/ventes/factures/gaps-numerotation/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        self.assertEqual(len(r.data['gaps']), 1)
        # Un responsable (non-admin) ne voit pas le rapport.
        api_resp = auth(self.resp)
        r2 = api_resp.get('/api/django/ventes/factures/gaps-numerotation/')
        self.assertEqual(r2.status_code, 403)
