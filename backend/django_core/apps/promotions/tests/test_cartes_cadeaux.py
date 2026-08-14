"""NTRET15 — Cartes cadeaux (émission, solde, expiration, utilisation
multi-passage).

Couvre : émission encaisse le montant exact, utilisation décrémente le solde
sur plusieurs passages jusqu'à épuisement (jamais en négatif), carte
épuisée/expirée refusée en paiement, isolation multi-tenant. Intégration
caisse : ``apps.pos.services.valider_vente`` accepte le mode
``carte_cadeau`` et débite réellement la carte dans la même transaction.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services as pos_services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.promotions import services as promo_services
from apps.promotions.models import CarteCadeau
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CarteCadeauServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret15', 'NTRET15 Co')

    def test_emettre_carte_cadeau_sets_initial_balance(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('500'))
        self.assertEqual(carte.montant_initial, Decimal('500'))
        self.assertEqual(carte.solde, Decimal('500'))
        self.assertEqual(carte.statut, CarteCadeau.Statut.ACTIVE)

    def test_emettre_carte_cadeau_code_generated_when_absent(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('100'))
        self.assertEqual(len(carte.code), 10)

    def test_emettre_carte_cadeau_physical_code_used_verbatim(self):
        carte = promo_services.emettre_carte_cadeau(
            self.co, Decimal('100'), code='PHYS-0001')
        self.assertEqual(carte.code, 'PHYS-0001')

    def test_emettre_carte_cadeau_requires_positive_amount(self):
        with self.assertRaises(promo_services.CarteCadeauError):
            promo_services.emettre_carte_cadeau(self.co, Decimal('0'))

    def test_debiter_carte_cadeau_decrements_balance(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('300'))
        promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('120'))
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('180'))
        self.assertEqual(carte.statut, CarteCadeau.Statut.ACTIVE)

    def test_debiter_multiple_passages_jusqu_a_epuisement(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('100'))
        promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('40'))
        promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('35'))
        promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('25'))
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('0'))
        self.assertEqual(carte.statut, CarteCadeau.Statut.EPUISEE)

    def test_debiter_never_goes_negative(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('50'))
        with self.assertRaises(promo_services.CarteCadeauError):
            promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('60'))
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('50'))  # inchangé

    def test_debiter_epuisee_refused(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('20'))
        promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('20'))
        with self.assertRaises(promo_services.CarteCadeauError):
            promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('1'))

    def test_debiter_expiree_refused(self):
        carte = promo_services.emettre_carte_cadeau(
            self.co, Decimal('100'), date_expiration=datetime.date(2020, 1, 1))
        with self.assertRaises(promo_services.CarteCadeauError):
            promo_services.debiter_carte_cadeau(self.co, carte.code, Decimal('10'))

    def test_verifier_carte_cadeau_checks_solde_suffisant(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('30'))
        with self.assertRaises(promo_services.CarteCadeauError):
            promo_services.verifier_carte_cadeau(self.co, carte.code, montant=Decimal('50'))
        # Solde suffisant : ne lève pas.
        promo_services.verifier_carte_cadeau(self.co, carte.code, montant=Decimal('20'))

    def test_isolation_multi_tenant(self):
        co_b = make_company('ntret15-b', 'B')
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('100'))
        with self.assertRaises(promo_services.CarteCadeauError):
            promo_services.debiter_carte_cadeau(co_b, carte.code, Decimal('10'))


class CarteCadeauPosIntegrationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret15-pos', 'NTRET15 POS Co')
        self.user = make_user(self.co, 'ntret15-pos-user')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        self.categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Chargeur solaire', prix_vente=Decimal('150'),
            prix_achat=Decimal('80'), quantite_stock=10, categorie=self.categorie)

    def _vente(self, prix='150'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=f'VC-CG-{prix}', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(prix))
        return vente

    def test_valider_vente_accepts_carte_cadeau_payment_mode(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('200'))
        vente = self._vente(prix='150')
        pos_services.valider_vente(
            vente=vente,
            paiements=[{'mode': 'carte_cadeau', 'montant': '150', 'carte_code': carte.code}],
            user=self.user)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.VALIDEE)
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('50.00'))

    def test_valider_vente_refuses_insufficient_carte_cadeau_before_any_write(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('20'))
        vente = self._vente(prix='150')
        with self.assertRaises(pos_services.VenteComptoirError):
            pos_services.valider_vente(
                vente=vente,
                paiements=[{'mode': 'carte_cadeau', 'montant': '150', 'carte_code': carte.code}],
                user=self.user)
        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.BROUILLON)  # rien créé
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('20'))  # inchangée

    def test_valider_vente_multiple_passages_on_same_card(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('300'))
        vente1 = self._vente(prix='100')
        vente2 = self._vente(prix='120')
        pos_services.valider_vente(
            vente=vente1,
            paiements=[{'mode': 'carte_cadeau', 'montant': '100', 'carte_code': carte.code}],
            user=self.user)
        pos_services.valider_vente(
            vente=vente2,
            paiements=[{'mode': 'carte_cadeau', 'montant': '120', 'carte_code': carte.code}],
            user=self.user)
        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('80.00'))

    def test_emettre_carte_cadeau_comptoir_encaisse_exact_amount(self):
        carte, facture = pos_services.emettre_carte_cadeau_comptoir(
            company=self.co, montant=Decimal('250'),
            paiement={'mode': 'carte', 'montant': '250'}, user=self.user,
            client=self.client_obj)
        self.assertEqual(carte.solde, Decimal('250.00'))
        self.assertEqual(facture.montant_ttc, Decimal('250.00'))
        self.assertEqual(facture.paiements.count(), 1)
        self.assertEqual(facture.paiements.first().montant, Decimal('250.00'))

    def test_emettre_carte_cadeau_comptoir_amount_mismatch_refused(self):
        with self.assertRaises(pos_services.CarteCadeauPosError):
            pos_services.emettre_carte_cadeau_comptoir(
                company=self.co, montant=Decimal('250'),
                paiement={'mode': 'carte', 'montant': '200'}, user=self.user,
                client=self.client_obj)


class CarteCadeauApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret15-api', 'NTRET15 API Co')
        self.user = make_user(self.co, 'ntret15-api-user')
        self.client_obj = Client.objects.create(company=self.co, nom='Client API')

    def test_emettre_carte_cadeau_via_api(self):
        api = auth(self.user)
        resp = api.post('/api/django/pos/ventes/emettre-carte-cadeau/', {
            'montant': '400', 'client': self.client_obj.id,
            'paiement': {'mode': 'carte', 'montant': '400'},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['solde'], '400.00')

        carte = CarteCadeau.objects.get(code=resp.data['code'])
        self.assertEqual(carte.company_id, self.co.id)

    def test_payer_carte_cadeau_preview_does_not_consume(self):
        carte = promo_services.emettre_carte_cadeau(self.co, Decimal('80'))
        api = auth(self.user)
        vente_resp = api.post(
            '/api/django/pos/ventes/', {'client': self.client_obj.id}, format='json')
        vente_id = vente_resp.data['id']

        resp = api.post(
            f'/api/django/pos/ventes/{vente_id}/payer-carte-cadeau/',
            {'code': carte.code}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['solde'], '80.00')

        carte.refresh_from_db()
        self.assertEqual(carte.solde, Decimal('80'))  # non consommé (aperçu)
