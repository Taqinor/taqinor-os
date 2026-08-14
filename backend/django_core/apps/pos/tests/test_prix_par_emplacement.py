"""NTRET29 — Grille tarifaire par boutique/emplacement (prix différenciés
multi-sites).

Couvre : une boutique avec override facture au bon prix, une boutique sans
override utilise le prix catalogue inchangé, une session sans boutique
résout toujours le prix catalogue (comportement historique inchangé).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.crm.models import Client
from apps.parametres.models import BoutiquePos
from apps.pos import selectors, services
from apps.pos.models import PrixParEmplacement, VenteComptoir
from apps.stock.models import Categorie, EmplacementStock, Produit

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


def make_session_caisse(company, user, *, boutique=None):
    compta_services.seed_plan_comptable(company)
    compta_services.seed_journaux(company)
    compte_caisse = CompteTresorerie.objects.create(
        company=company, type_compte=CompteTresorerie.Type.CAISSE,
        libelle='Caisse comptoir',
        compte_comptable=compta_services.get_compte(company, '5161'))
    caisse_comptable = compta_services.creer_caisse(
        company, compte_caisse, libelle='Caisse POS', solde_initial=Decimal('0'))
    return services.ouvrir_session(
        company=company, caisse_comptable=caisse_comptable,
        caissier=user, fond_ouverture=Decimal('0'), user=user, boutique=boutique)


class PrixApplicableSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret29', 'NTRET29 Co')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble', prix_vente=Decimal('100'),
            prix_achat=Decimal('40'), quantite_stock=10, categorie=categorie)
        emplacement = EmplacementStock.objects.create(
            company=self.co, nom='Showroom Touristique')
        self.boutique = BoutiquePos.objects.create(
            company=self.co, emplacement=emplacement)

    def test_sans_override_repli_sur_le_prix_catalogue(self):
        prix = selectors.prix_applicable(self.co, self.produit, self.boutique)
        self.assertEqual(prix, Decimal('100'))

    def test_boutique_none_toujours_le_prix_catalogue(self):
        PrixParEmplacement.objects.create(
            company=self.co, produit=self.produit, boutique=self.boutique,
            prix_ttc=Decimal('130'))
        prix = selectors.prix_applicable(self.co, self.produit, None)
        self.assertEqual(prix, Decimal('100'))

    def test_avec_override_renvoie_le_prix_boutique(self):
        PrixParEmplacement.objects.create(
            company=self.co, produit=self.produit, boutique=self.boutique,
            prix_ttc=Decimal('130'))
        prix = selectors.prix_applicable(self.co, self.produit, self.boutique)
        self.assertEqual(prix, Decimal('130'))


class PrixParEmplacementIntegrationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret29-int', 'NTRET29 Int Co')
        self.user = make_user(self.co, 'caissier-ntret29')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble', prix_vente=Decimal('100'),
            prix_achat=Decimal('40'), quantite_stock=10, categorie=categorie)
        emplacement = EmplacementStock.objects.create(
            company=self.co, nom='Showroom Touristique')
        self.boutique = BoutiquePos.objects.create(
            company=self.co, emplacement=emplacement)
        PrixParEmplacement.objects.create(
            company=self.co, produit=self.produit, boutique=self.boutique,
            prix_ttc=Decimal('130'))

    def test_ajouter_ligne_avec_boutique_facture_au_bon_prix(self):
        session = make_session_caisse(self.co, self.user, boutique=self.boutique)
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-PPE-1', client=self.client_obj,
            created_by=self.user, session_caisse=session)
        api = auth(self.user)
        res = api.post(
            f'/api/django/pos/ventes/{vente.id}/lignes/',
            {'produit': self.produit.id, 'quantite': 1})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['prix_unitaire_ttc']), Decimal('130.00'))

    def test_ajouter_ligne_sans_boutique_prix_catalogue_inchange(self):
        session = make_session_caisse(self.co, self.user, boutique=None)
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-PPE-2', client=self.client_obj,
            created_by=self.user, session_caisse=session)
        api = auth(self.user)
        res = api.post(
            f'/api/django/pos/ventes/{vente.id}/lignes/',
            {'produit': self.produit.id, 'quantite': 1})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['prix_unitaire_ttc']), Decimal('100.00'))

    def test_prix_explicite_dans_la_requete_garde_priorite(self):
        session = make_session_caisse(self.co, self.user, boutique=self.boutique)
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-PPE-3', client=self.client_obj,
            created_by=self.user, session_caisse=session)
        api = auth(self.user)
        res = api.post(
            f'/api/django/pos/ventes/{vente.id}/lignes/',
            {'produit': self.produit.id, 'quantite': 1, 'prix_unitaire_ttc': '999'})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['prix_unitaire_ttc']), Decimal('999.00'))

    def test_ouvrir_session_refuse_boutique_dune_autre_societe(self):
        co_b = make_company('ntret29-b', 'NTRET29 B')
        emplacement_b = EmplacementStock.objects.create(company=co_b, nom='Autre')
        boutique_b = BoutiquePos.objects.create(company=co_b, emplacement=emplacement_b)
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        caisse_comptable = compta_services.creer_caisse(
            self.co, compte_caisse, libelle='Caisse POS', solde_initial=Decimal('0'))
        with self.assertRaises(services.SessionCaisseError):
            services.ouvrir_session(
                company=self.co, caisse_comptable=caisse_comptable,
                caissier=self.user, fond_ouverture=Decimal('0'), user=self.user,
                boutique=boutique_b)
