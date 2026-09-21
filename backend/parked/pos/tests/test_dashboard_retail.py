"""NTRET16 — Tableau de bord retail (panier moyen, transformation,
ventes/m², top produits/catégories/vendeurs, comparatif boutiques).

Couvre : les 5 KPI se calculent juste sur un jeu de données multi-boutiques,
marge invisible sans permission, export xlsx.
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
from apps.pos.models import LigneVenteComptoir, VenteComptoir
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


def make_session_caisse(company, user, libelle):
    compta_services.seed_plan_comptable(company)
    compta_services.seed_journaux(company)
    compte_caisse = CompteTresorerie.objects.create(
        company=company, type_compte=CompteTresorerie.Type.CAISSE,
        libelle=libelle, compte_comptable=compta_services.get_compte(company, '5161'))
    caisse_comptable = compta_services.creer_caisse(
        company, compte_caisse, libelle=libelle, solde_initial=Decimal('0'))
    return services.ouvrir_session(
        company=company, caisse_comptable=caisse_comptable,
        caissier=user, fond_ouverture=Decimal('0'), user=user)


class DashboardRetailSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret16', 'NTRET16 Co')
        self.user = make_user(self.co, 'caissier-ntret16')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        self.categorie = Categorie.objects.create(company=self.co, nom='Onduleurs')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur 3kW', prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'), quantite_stock=50, categorie=self.categorie)

        self.session_casa = make_session_caisse(self.co, self.user, 'Caisse Casablanca')
        self.session_rabat = make_session_caisse(self.co, self.user, 'Caisse Rabat')

        self._vente(self.session_casa, montant='1000')
        self._vente(self.session_rabat, montant='500')

        emplacement = EmplacementStock.objects.create(
            company=self.co, nom='Showroom Casa')
        BoutiquePos.objects.create(
            company=self.co, emplacement=emplacement, surface_m2=Decimal('100'))

    def _vente(self, session, montant='1000'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=f'VC-RET-{session.id}-{montant}',
            client=self.client_obj, created_by=self.user, session_caisse=session)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal(montant))
        services.valider_vente(
            vente=vente, paiements=[{'mode': 'carte', 'montant': montant}],
            user=self.user)

    def test_panier_moyen(self):
        data = selectors.dashboard_retail(company=self.co)
        self.assertEqual(data['nb_ventes'], 2)
        self.assertEqual(Decimal(data['panier_moyen']), Decimal('750.00'))

    def test_taux_transformation_counts_brouillon_as_unconverted(self):
        # Un panier créé (brouillon) mais jamais validé — proxy du panier
        # non converti (les tickets parqués XPOS2 sont client-side only).
        VenteComptoir.objects.create(
            company=self.co, reference='VC-RET-BROUILLON', client=self.client_obj,
            created_by=self.user)
        data = selectors.dashboard_retail(company=self.co)
        # 2 validées / (2 validées + 1 brouillon) = 66.67%
        self.assertEqual(Decimal(data['taux_transformation_pct']), Decimal('66.67'))

    def test_taux_transformation_100_pct_without_brouillon(self):
        data = selectors.dashboard_retail(company=self.co)
        self.assertEqual(Decimal(data['taux_transformation_pct']), Decimal('100.00'))

    def test_ventes_par_m2(self):
        data = selectors.dashboard_retail(company=self.co)
        # Total 1500 MAD / 100 m² = 15.00
        self.assertEqual(Decimal(data['ventes_par_m2']), Decimal('15.00'))

    def test_ventes_par_m2_none_without_surface(self):
        BoutiquePos.objects.all().delete()
        data = selectors.dashboard_retail(company=self.co)
        self.assertIsNone(data['ventes_par_m2'])

    def test_top_produits_categories_vendeurs(self):
        data = selectors.dashboard_retail(company=self.co)
        self.assertEqual(data['top_produits'][0]['nom'], 'Onduleur 3kW')
        self.assertEqual(Decimal(data['top_produits'][0]['total']), Decimal('1500.00'))
        self.assertEqual(data['top_categories'][0]['nom'], 'Onduleurs')
        self.assertEqual(data['top_vendeurs'][0]['nom'], 'caissier-ntret16')

    def test_comparatif_boutiques_multi_sites(self):
        data = selectors.dashboard_retail(company=self.co)
        comparatif = data['comparatif_boutiques']
        self.assertEqual(Decimal(comparatif['Caisse Casablanca']), Decimal('1000.00'))
        self.assertEqual(Decimal(comparatif['Caisse Rabat']), Decimal('500.00'))

    def test_filter_by_boutique(self):
        data = selectors.dashboard_retail(company=self.co, boutique='Caisse Rabat')
        self.assertEqual(data['nb_ventes'], 1)
        self.assertEqual(Decimal(data['total_ttc']), Decimal('500.00'))

    def test_marge_absent_without_include_marge(self):
        data = selectors.dashboard_retail(company=self.co, include_marge=False)
        for row in data['top_produits']:
            self.assertNotIn('marge', row)

    def test_export_xlsx_never_contains_prix_achat(self):
        response = selectors.export_dashboard_retail_xlsx(company=self.co)
        content = response.content
        self.assertNotIn(b'prix_achat', content)
        self.assertNotIn(b'600', content)


class DashboardRetailApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret16-api', 'NTRET16 API Co')
        self.admin = make_user(self.co, 'admin-ntret16', role='admin')

    def test_dashboard_retail_endpoint(self):
        api = auth(self.admin)
        resp = api.get('/api/django/pos/ventes/dashboard-retail/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('taux_transformation_pct', resp.data)
        self.assertIn('comparatif_boutiques', resp.data)

    def test_dashboard_retail_export_endpoint(self):
        api = auth(self.admin)
        resp = api.get('/api/django/pos/ventes/dashboard-retail-export/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet')
