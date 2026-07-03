"""XPOS1 — Vente comptoir : validation → facture + paiement + stock + timbre.

Couvre : POST /api/django/pos/ventes/ crée facture+paiement+mouvement stock+
timbre en une transaction, scoping multi-tenant, remise au-delà du seuil
refusée sans approbation, prix_achat jamais sérialisé.
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
from apps.parametres.models import CompanyProfile
from apps.pos import services
from apps.pos.models import VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_session_caisse(company, user):
    """Ouvre une session de caisse (XPOS4) — requise pour tout règlement
    espèces (cf. services.valider_vente)."""
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
        caissier=user, fond_ouverture=Decimal('0'), user=user)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client_(company, nom='Client Test'):
    return Client.objects.create(company=company, nom=nom)


def make_produit(company, nom='Câble solaire', prix_vente='100', prix_achat='40',
                 stock=10):
    categorie = Categorie.objects.create(company=company, nom='Accessoires')
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=Decimal(prix_vente),
        prix_achat=Decimal(prix_achat), quantite_stock=stock,
        categorie=categorie)


class ValiderVenteServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xpos1', 'XPOS1 Co')
        self.user = make_user(self.co, 'caissier1')
        self.client_obj = make_client_(self.co)
        self.produit = make_produit(self.co)

    def _vente(self, *, remise=0):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-000001', client=self.client_obj,
            created_by=self.user)
        from apps.pos.models import LigneVenteComptoir
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=2, prix_unitaire_ttc=Decimal('120'), remise=remise)
        return vente

    def test_valider_vente_creates_facture_paiement_stock_timbre(self):
        vente = self._vente()
        session = make_session_caisse(self.co, self.user)
        vente.session_caisse = session
        vente.save(update_fields=['session_caisse'])
        paiements = [{'mode': 'especes', 'montant': '240'}]
        services.valider_vente(vente=vente, paiements=paiements, user=self.user)

        vente.refresh_from_db()
        self.assertEqual(vente.statut, VenteComptoir.Statut.VALIDEE)
        self.assertIsNotNone(vente.facture)
        self.assertEqual(vente.facture.montant_ttc, Decimal('240.00'))
        self.assertEqual(vente.facture.client_id, self.client_obj.id)

        # Paiement enregistré sur la facture.
        self.assertEqual(vente.facture.paiements.count(), 1)
        self.assertEqual(vente.facture.paiements.first().montant, Decimal('240.00'))

        # Stock décrémenté immédiatement.
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 8)

        # Droit de timbre posé (règlement espèces).
        from apps.compta.models import TimbreFiscal
        self.assertEqual(
            TimbreFiscal.objects.filter(company=self.co).count(), 1)

    def test_valider_vente_carte_no_timbre(self):
        vente = self._vente()
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '240'}],
            user=self.user)
        from apps.compta.models import TimbreFiscal
        self.assertEqual(
            TimbreFiscal.objects.filter(company=self.co).count(), 0)

    def test_valider_vente_requires_lines(self):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-000002', client=self.client_obj,
            created_by=self.user)
        with self.assertRaises(services.VenteComptoirError):
            services.valider_vente(
                vente=vente, paiements=[{'mode': 'carte', 'montant': '1'}],
                user=self.user)

    def test_valider_vente_requires_client(self):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-000003', created_by=self.user)
        from apps.pos.models import LigneVenteComptoir
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal('50'))
        with self.assertRaises(services.VenteComptoirError):
            services.valider_vente(
                vente=vente, paiements=[{'mode': 'carte', 'montant': '50'}],
                user=self.user)

    def test_remise_over_threshold_refused_without_approval(self):
        profile = CompanyProfile.get(company=self.co)
        profile.discount_approval_threshold = Decimal('10')
        profile.save(update_fields=['discount_approval_threshold'])
        vente = self._vente(remise=25)
        with self.assertRaises(services.VenteComptoirError):
            services.valider_vente(
                vente=vente, paiements=[{'mode': 'carte', 'montant': '180'}],
                user=self.user)

    def test_prix_achat_never_serialized(self):
        vente = self._vente()
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': '240'}],
            user=self.user)
        # Le prix d'achat du produit porte une valeur DISTINCTIVE (43.17) qui
        # n'est sous-chaîne d'aucun montant légitime sérialisé (240.00/200.00/…),
        # pour que la vérification de non-fuite ne soit pas un faux positif sur
        # « 40.00 » présent dans « 240.00 ».
        self.produit.prix_achat = Decimal('43.17')
        self.produit.save(update_fields=['prix_achat'])
        from apps.pos.serializers import VenteComptoirSerializer
        data = VenteComptoirSerializer(vente).data
        as_str = str(data)
        self.assertNotIn('prix_achat', as_str)
        self.assertNotIn('43.17', as_str)  # prix_achat value never leaks

    def test_especes_requires_open_session(self):
        vente = self._vente()
        vente.session_caisse = None
        vente.save()
        with self.assertRaises(services.VenteComptoirError):
            services.valider_vente(
                vente=vente, paiements=[{'mode': 'especes', 'montant': '240'}],
                user=self.user)


class VenteComptoirApiTests(TestCase):
    BASE = '/api/django/pos/ventes/'

    def setUp(self):
        self.co_a = make_company('xpos1-a', 'A')
        self.co_b = make_company('xpos1-b', 'B')
        self.user_a = make_user(self.co_a, 'xpos1-a-user')
        self.user_b = make_user(self.co_b, 'xpos1-b-user')
        self.client_a = make_client_(self.co_a, 'Client A')
        self.produit_a = make_produit(self.co_a)

    def _rows(self, resp):
        data = resp.data
        return data['results'] if isinstance(data, dict) and 'results' in data else data

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {'client': self.client_a.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        vente = VenteComptoir.objects.get(id=resp.data['id'])
        self.assertEqual(vente.company_id, self.co_a.id)
        self.assertTrue(vente.reference)

    def test_company_isolation(self):
        api_a = auth(self.user_a)
        resp = api_a.post(self.BASE, {'client': self.client_a.id}, format='json')
        vente_id = resp.data['id']

        api_b = auth(self.user_b)
        detail = api_b.get(f'{self.BASE}{vente_id}/')
        self.assertEqual(detail.status_code, 404)

    def test_full_flow_via_api(self):
        api = auth(self.user_a)
        create_resp = api.post(
            self.BASE, {'client': self.client_a.id}, format='json')
        vente_id = create_resp.data['id']

        ligne_resp = api.post(
            f'{self.BASE}{vente_id}/lignes/',
            {'produit': self.produit_a.id, 'quantite': 1,
             'prix_unitaire_ttc': '100'},
            format='json')
        self.assertEqual(ligne_resp.status_code, 201, ligne_resp.data)

        valider_resp = api.post(
            f'{self.BASE}{vente_id}/valider/',
            {'paiements': [{'mode': 'carte', 'montant': '100'}]},
            format='json')
        self.assertEqual(valider_resp.status_code, 200, valider_resp.data)
        self.assertEqual(valider_resp.data['statut'], 'validee')
        self.assertIsNotNone(valider_resp.data['facture'])
