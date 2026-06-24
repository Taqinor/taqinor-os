"""FG52 — Multi-currency quoting/invoicing.

Tests :
  * Devis.devise / taux_change ont les bonnes valeurs par défaut (MAD / 1).
  * Facture.devise / taux_change pareil.
  * CompanyProfile.devise_defaut défaut MAD.
  * L'API /devis/ crée un devis avec la devise MAD par défaut.
  * L'API /devis/ crée un devis avec une devise EUR explicite.
  * L'API /factures/ crée une facture avec la devise EUR snapshotée.
  * build_ubl_xml (dgi_export) lit facture.devise → DocumentCurrencyCode.
  * Multi-tenant : un user de company B ne peut pas lire les devis de company A.
  * build_quote_data passe la devise dans le dict renvoyé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
from apps.ventes.dgi.dgi_export import build_ubl_xml

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom='Test Co'):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x',
        role_legacy=role, company=company,
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client(company, email):
    return Client.objects.create(
        company=company, nom='Test', prenom='Client',
        email=email, telephone='+212600000099', adresse='Casa',
    )


def make_produit(company):
    return Produit.objects.create(
        company=company, nom='Panneau 450W', sku='FG52-PV',
        prix_vente=Decimal('5000'), quantite_stock=10,
        tva=Decimal('20.00'),
    )


def make_devis(company, client, reference=None, devise='MAD', taux_change=1):
    ref = reference or f'DEV-{MONTH}-FG52'
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut=Devis.Statut.BROUILLON,
        taux_tva=Decimal('20.00'),
        devise=devise, taux_change=Decimal(str(taux_change)),
    )


class TestDevisDeviseDefault(TestCase):
    """Devis.devise et taux_change ont les valeurs par défaut attendues."""

    def setUp(self):
        self.company = make_company('fg52-a')
        self.client_obj = make_client(self.company, 'a@fg52.ma')

    def test_devise_defaut_mad(self):
        devis = Devis.objects.create(
            company=self.company,
            reference=f'DEV-{MONTH}-D1',
            client=self.client_obj,
            statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'),
        )
        self.assertEqual(devis.devise, 'MAD')
        self.assertEqual(devis.taux_change, Decimal('1'))

    def test_devise_eur_sauvee(self):
        devis = make_devis(
            self.company, self.client_obj,
            reference=f'DEV-{MONTH}-D2',
            devise='EUR', taux_change=10.7,
        )
        devis.refresh_from_db()
        self.assertEqual(devis.devise, 'EUR')
        self.assertAlmostEqual(float(devis.taux_change), 10.7, places=4)


class TestFactureDevise(TestCase):
    """Facture.devise et taux_change."""

    def setUp(self):
        self.company = make_company('fg52-b')
        self.client_obj = make_client(self.company, 'b@fg52.ma')

    def test_facture_devise_defaut_mad(self):
        facture = Facture.objects.create(
            company=self.company,
            reference=f'FAC-{MONTH}-F1',
            client=self.client_obj,
            statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'),
        )
        self.assertEqual(facture.devise, 'MAD')
        self.assertEqual(facture.taux_change, Decimal('1'))

    def test_facture_devise_eur(self):
        facture = Facture.objects.create(
            company=self.company,
            reference=f'FAC-{MONTH}-F2',
            client=self.client_obj,
            statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'),
            devise='EUR', taux_change=Decimal('10.70'),
        )
        facture.refresh_from_db()
        self.assertEqual(facture.devise, 'EUR')
        self.assertEqual(facture.taux_change, Decimal('10.700000'))


class TestCompanyProfileDeviseDefaut(TestCase):
    """CompanyProfile.devise_defaut défaut MAD."""

    def test_devise_defaut_mad(self):
        company = make_company('fg52-p')
        profile = CompanyProfile.get(company=company)
        self.assertEqual(profile.devise_defaut, 'MAD')

    def test_devise_defaut_editable(self):
        company = make_company('fg52-p2')
        profile = CompanyProfile.get(company=company)
        profile.devise_defaut = 'EUR'
        profile.save(update_fields=['devise_defaut'])
        profile.refresh_from_db()
        self.assertEqual(profile.devise_defaut, 'EUR')


class TestDevisAPIDevise(TestCase):
    """L'API /devis/ accepte et retourne devise + taux_change."""

    def setUp(self):
        self.company = make_company('fg52-api-a')
        self.user = make_user(self.company, 'fg52_api_a')
        self.api = auth(self.user)
        self.client_obj = make_client(self.company, 'api-a@fg52.ma')
        self.produit = make_produit(self.company)

    def test_api_creer_devis_devise_defaut_mad(self):
        payload = {
            'client': self.client_obj.id,
            'taux_tva': '20.00',
        }
        resp = self.api.post('/api/django/ventes/devis/', payload, format='json')
        self.assertIn(resp.status_code, (200, 201))
        data = resp.json()
        self.assertEqual(data.get('devise'), 'MAD')
        self.assertEqual(str(data.get('taux_change')), '1.000000')

    def test_api_creer_devis_devise_eur(self):
        payload = {
            'client': self.client_obj.id,
            'taux_tva': '20.00',
            'devise': 'EUR',
            'taux_change': '10.700000',
        }
        resp = self.api.post('/api/django/ventes/devis/', payload, format='json')
        self.assertIn(resp.status_code, (200, 201))
        data = resp.json()
        self.assertEqual(data.get('devise'), 'EUR')

    def test_api_liste_devis_inclut_devise(self):
        make_devis(
            self.company, self.client_obj,
            reference=f'DEV-{MONTH}-API1',
            devise='USD', taux_change=10.0,
        )
        resp = self.api.get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        # Support both paginated and plain list shapes.
        if isinstance(results, dict):
            results = results.get('results', [])
        self.assertTrue(len(results) >= 1)
        first = results[0]
        self.assertIn('devise', first)
        self.assertIn('taux_change', first)


class TestCompanyDeviseDefautApplique(TestCase):
    """Régression FG52 : la devise par défaut de la société
    (``CompanyProfile.devise_defaut``) pilote RÉELLEMENT les nouveaux devis et
    factures créés via l'API quand le corps n'envoie pas de devise ; une devise
    explicite reste prioritaire et une autre société reste en MAD."""

    def setUp(self):
        self.co_eur = make_company('fg52-defeur')
        self.co_mad = make_company('fg52-defmad')
        self.user_eur = make_user(self.co_eur, 'fg52_def_eur')
        self.user_mad = make_user(self.co_mad, 'fg52_def_mad')
        self.client_eur = make_client(self.co_eur, 'def-eur@fg52.ma')
        self.client_mad = make_client(self.co_mad, 'def-mad@fg52.ma')
        prof = CompanyProfile.get(company=self.co_eur)
        prof.devise_defaut = 'EUR'
        prof.save(update_fields=['devise_defaut'])

    def test_devis_herite_devise_defaut_societe(self):
        api = auth(self.user_eur)
        resp = api.post(
            '/api/django/ventes/devis/',
            {'client': self.client_eur.id, 'taux_tva': '20.00'},
            format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        self.assertEqual(resp.json().get('devise'), 'EUR')

    def test_facture_herite_devise_defaut_societe(self):
        api = auth(self.user_eur)
        resp = api.post(
            '/api/django/ventes/factures/',
            {'client': self.client_eur.id, 'taux_tva': '20.00'},
            format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        self.assertEqual(resp.json().get('devise'), 'EUR')

    def test_devise_explicite_prime_sur_defaut_societe(self):
        api = auth(self.user_eur)
        resp = api.post(
            '/api/django/ventes/devis/',
            {'client': self.client_eur.id, 'taux_tva': '20.00',
             'devise': 'USD'},
            format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        self.assertEqual(resp.json().get('devise'), 'USD')

    def test_autre_societe_reste_mad(self):
        api = auth(self.user_mad)
        resp = api.post(
            '/api/django/ventes/devis/',
            {'client': self.client_mad.id, 'taux_tva': '20.00'},
            format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        self.assertEqual(resp.json().get('devise'), 'MAD')


class TestMultiTenantIsolation(TestCase):
    """Un user de company B ne doit pas voir les devis de company A."""

    def setUp(self):
        self.co_a = make_company('fg52-mt-a')
        self.co_b = make_company('fg52-mt-b')
        self.user_a = make_user(self.co_a, 'fg52_mt_a')
        self.user_b = make_user(self.co_b, 'fg52_mt_b')
        self.client_a = make_client(self.co_a, 'mt-a@fg52.ma')
        self.client_b = make_client(self.co_b, 'mt-b@fg52.ma')
        make_devis(self.co_a, self.client_a, reference=f'DEV-{MONTH}-MTA')
        make_devis(self.co_b, self.client_b, reference=f'DEV-{MONTH}-MTB')

    def test_user_b_ne_voit_pas_devis_a(self):
        api_b = auth(self.user_b)
        resp = api_b.get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        if isinstance(results, dict):
            results = results.get('results', [])
        refs = [r['reference'] for r in results]
        # Company B's user must not see company A's devis.
        self.assertNotIn(f'DEV-{MONTH}-MTA', refs)
        self.assertIn(f'DEV-{MONTH}-MTB', refs)


class TestDgiExportDevise(TestCase):
    """build_ubl_xml utilise facture.devise → DocumentCurrencyCode."""

    def setUp(self):
        self.company = make_company('fg52-dgi')
        self.user = make_user(self.company, 'fg52_dgi')
        self.client_obj = make_client(self.company, 'dgi@fg52.ma')
        profile = CompanyProfile.get(company=self.company)
        profile.nom = 'Taqinor Test'
        profile.ice = 'ICE-FG52-001'
        profile.save()
        self.profile = profile
        self.produit = make_produit(self.company)

    def _make_facture(self, devise='MAD', taux_change=1):
        facture = Facture.objects.create(
            company=self.company,
            reference=f'FAC-{MONTH}-DGI1',
            client=self.client_obj,
            statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            devise=devise,
            taux_change=Decimal(str(taux_change)),
        )
        LigneFacture.objects.create(
            facture=facture,
            produit=self.produit,
            designation='Panneau 450W',
            quantite=Decimal('5'),
            prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'),
        )
        return facture

    def test_ubl_xml_devise_mad_defaut(self):
        facture = self._make_facture(devise='MAD')
        xml = build_ubl_xml(facture, profile=self.profile)
        self.assertIn('<cbc:DocumentCurrencyCode>MAD</cbc:DocumentCurrencyCode>', xml)

    def test_ubl_xml_devise_eur(self):
        facture = self._make_facture(devise='EUR', taux_change=10.7)
        xml = build_ubl_xml(facture, profile=self.profile)
        self.assertIn('<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>', xml)

    def test_ubl_xml_currency_param_overrides_facture_devise(self):
        """Rétro-compat : un currency explicite prend la précédence sur facture.devise."""
        facture = self._make_facture(devise='EUR')
        xml = build_ubl_xml(facture, profile=self.profile, currency='USD')
        self.assertIn('<cbc:DocumentCurrencyCode>USD</cbc:DocumentCurrencyCode>', xml)


class TestBuildQuoteDataDevise(TestCase):
    """build_quote_data inclut 'devise' et 'taux_change' dans le dict renvoyé."""

    def setUp(self):
        self.company = make_company('fg52-bqd')
        self.client_obj = make_client(self.company, 'bqd@fg52.ma')
        self.produit = make_produit(self.company)

    def _make_devis_with_ligne(self, devise='MAD', taux_change=1):
        devis = make_devis(
            self.company, self.client_obj,
            reference=f'DEV-{MONTH}-BQD1',
            devise=devise, taux_change=taux_change,
        )
        LigneDevis.objects.create(
            devis=devis, produit=self.produit,
            designation='Onduleur 5kW réseau',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'),
        )
        return devis

    def test_build_quote_data_inclut_devise_mad(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._make_devis_with_ligne()
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data.get('devise'), 'MAD')
        self.assertEqual(data.get('taux_change'), 1.0)

    def test_build_quote_data_inclut_devise_eur(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._make_devis_with_ligne(devise='EUR', taux_change=10.7)
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(data.get('devise'), 'EUR')
        self.assertAlmostEqual(data.get('taux_change'), 10.7, places=4)
