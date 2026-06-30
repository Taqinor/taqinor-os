"""FG272 — tests du générateur de déclaration de raccordement BT/MT.

Couvre : pré-remplissage (client/site/kWc/onduleur/schéma) depuis un devis,
classement BT/MT, endpoint JSON scopé société, ne change aucun statut de devis,
aucun prix d'achat exposé.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg272_declaration -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, LigneDevis
from apps.ventes.connection_declaration import build_declaration_data
from apps.crm.models import Client
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Sefrioui', prenom='Hamza',
        email=f'h_{company.slug}@example.com', telephone='+212644444444',
        adresse='12 rue des Palmiers, Casablanca', ice='001234567000089')


def make_devis_with_system(company, user, ref='DEV-FG272-1'):
    client = make_client_obj(company)
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user, taux_tva=Decimal('20'))
    panel = Produit.objects.create(
        company=company, nom='Panneau 550W', prix_vente=Decimal('1500'),
        prix_achat=Decimal('900'))
    ond = Produit.objects.create(
        company=company, nom='Onduleur 10kW', prix_vente=Decimal('12000'),
        prix_achat=Decimal('8000'))
    LigneDevis.objects.create(
        devis=devis, produit=panel, designation='Panneau 550W mono',
        quantite=Decimal('18'), prix_unitaire=Decimal('1500'))
    LigneDevis.objects.create(
        devis=devis, produit=ond, designation='Onduleur réseau 10kW',
        quantite=Decimal('1'), prix_unitaire=Decimal('12000'))
    return devis


class BuildDeclarationDataTest(TestCase):
    def test_prefills_client_and_system(self):
        co = make_company('decl-build')
        user = make_user(co, 'decl_b')
        devis = make_devis_with_system(co, user)
        data = build_declaration_data(devis, regime_8221='declaration_bt')
        self.assertEqual(data['devis_reference'], 'DEV-FG272-1')
        self.assertIn('Sefrioui', data['client']['nom'])
        self.assertEqual(data['client']['ice'], '001234567000089')
        # 18 × 550 W = 9.9 kWc.
        self.assertAlmostEqual(data['systeme']['kwc'], 9.9, places=1)
        self.assertEqual(data['systeme']['n_panneaux'], 18)
        self.assertTrue(data['systeme']['onduleur'])
        # Régime → pièces présentes.
        self.assertTrue(len(data['pieces']) > 0)

    def test_no_buy_price_in_output(self):
        co = make_company('decl-noprice')
        user = make_user(co, 'decl_np')
        devis = make_devis_with_system(co, user)
        data = build_declaration_data(devis, regime_8221='declaration_bt')
        blob = repr(data)
        for forbidden in ('900', '8000', 'prix_achat', 'marge'):
            self.assertNotIn(forbidden, blob)


class DeclarationEndpointTest(TestCase):
    def setUp(self):
        self.company = make_company('decl-acme')
        self.other = make_company('decl-other')
        self.user = make_user(self.company, 'decl_user')
        self.devis = make_devis_with_system(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = (f'/api/django/ventes/devis/{self.devis.id}/'
                    f'declaration-raccordement/')

    def test_json_prefill(self):
        resp = self.api.get(self.url, {'regime': 'declaration_bt'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['raccordement'], 'BT')
        self.assertAlmostEqual(resp.data['systeme']['kwc'], 9.9, places=1)
        # Le statut du devis n'a pas changé (lecture seule, RULE #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')

    def test_other_company_devis_404(self):
        other_user = make_user(self.other, 'decl_o')
        other_devis = make_devis_with_system(
            self.other, other_user, ref='DEV-OTHER-DECL')
        url = (f'/api/django/ventes/devis/{other_devis.id}/'
               f'declaration-raccordement/')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)
