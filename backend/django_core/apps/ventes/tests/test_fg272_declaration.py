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
        # CIQ615 — aucun niveau connu (ni chantier ni lead) : champ vide.
        self.assertEqual(resp.data['raccordement'], '')
        self.assertAlmostEqual(resp.data['systeme']['kwc'], 9.9, places=1)
        # Le statut du devis n'a pas changé (lecture seule, RULE #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')

    def test_regime_et_format_enumeres_400(self):
        # CI #997 fuzz (24/10) : ``regime`` et ``format`` ont une énumération
        # PUBLIÉE ; vide ou hors liste (dont un caractère de contrôle) = 400.
        for params in ({'regime': ''}, {'regime': 'zzz'}, {'format': ''},
                       {'format': 'docx'}):
            with self.subTest(params=params):
                resp = self.api.get(self.url, params)
                self.assertIn(resp.status_code, (400, 404), resp.content)
        resp = self.api.get(self.url, {'regime': 'a_qualifier'})
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_other_company_devis_404(self):
        other_user = make_user(self.other, 'decl_o')
        other_devis = make_devis_with_system(
            self.other, other_user, ref='DEV-OTHER-DECL')
        url = (f'/api/django/ventes/devis/{other_devis.id}/'
               f'declaration-raccordement/')
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_lecture_exige_un_code_ventes(self):
        """ADRG9 (D-APFS-4) — la déclaration se lit par la lecture du module
        ventes : Commercial terrain et Admin RH livrés (aucun code ventes)
        reçoivent 403, JSON comme PDF, sans rendu ; le Commercial auteur
        obtient la déclaration de son devis."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            ADMIN_RH_PERMISSIONS, COMMERCIAL_PERMISSIONS,
            COMMERCIAL_TERRAIN_PERMISSIONS,
        )

        def compte(nom, perms):
            user = User.objects.create_user(
                username=f'adrg9-{len(nom)}-{nom[:5]}', password='x',
                company=self.company, role=Role.objects.create(
                    company=self.company, nom=nom, permissions=list(perms)))
            api = APIClient()
            api.force_authenticate(user)
            return user, api

        for nom, perms in (('Commercial terrain', COMMERCIAL_TERRAIN_PERMISSIONS),
                           ('Admin RH', ADMIN_RH_PERMISSIONS)):
            _user, api = compte(nom, perms)
            resp = api.get(self.url)
            self.assertEqual(resp.status_code, 403, (nom, resp.content))
            # ``?format=pdf`` est capté AVANT les permissions par la négociation
            # de format de DRF (``URL_FORMAT_OVERRIDE``, aucun rendu « pdf ») :
            # 404, jamais un PDF rendu.
            resp = api.get(self.url, {'format': 'pdf'})
            self.assertIn(resp.status_code, (403, 404), (nom, resp.content))
            self.assertNotEqual(resp.get('Content-Type'), 'application/pdf')
        commercial, api = compte('Commercial', COMMERCIAL_PERMISSIONS)
        Devis.objects.filter(pk=self.devis.pk).update(created_by=commercial)
        resp = api.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertAlmostEqual(resp.data['systeme']['kwc'], 9.9, places=1)
