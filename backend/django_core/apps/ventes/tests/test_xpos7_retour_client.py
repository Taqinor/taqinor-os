"""XPOS7 — Retour client avec re-stockage (contre ticket/facture d'origine).

Couvre :
  * un retour partiel crée l'avoir exact + re-stocke les quantités choisies
    (MouvementStock ENTREE + `Produit.quantite_stock` mis à jour) ;
  * un retour SANS re-stockage reste possible (`restocker=False`) : avoir
    créé, stock inchangé ;
  * motif de retour obligatoire (400 sans motif) ;
  * quantité retournée > quantité vendue refusée (400), y compris en tenant
    compte d'un retour déjà acté sur la même ligne (pas de double retour) ;
  * scoping company (isolation cross-tenant).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit, MouvementStock
from apps.ventes.models import Avoir, Facture, LigneFacture

User = get_user_model()


def make_company(slug='xpos7-co', nom='XPOS7 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestRetourClient(TestCase):
    def setUp(self):
        from apps.roles.models import Role, RESPONSABLE_PERMISSIONS
        self.company = make_company()
        resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.resp = User.objects.create_user(
            username='xpos7_resp', password='x', role=resp_role,
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XPOS7',
            telephone='+212600000007')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='XPOS7-PV1',
            prix_vente=Decimal('1000'), quantite_stock=50, tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-XPOS7-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_retour_partiel_avec_restockage(self):
        api = self._api(self.resp)
        qte_avant = self.panneau.quantite_stock
        r = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': 'Article endommagé à réception',
                'restocker': True,
                'lignes': [{'produit': self.panneau.id, 'quantite': '3'}],
            }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        avoir = Avoir.objects.get(id=r.data['id'])
        self.assertTrue(avoir.restocke)
        self.assertEqual(avoir.motif_retour, 'Article endommagé à réception')
        # 3 × 1000 HT × 1.20 TVA = 3600 TTC
        self.assertEqual(avoir.total_ttc, Decimal('3600.00'))
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, qte_avant + 3)
        mvt = MouvementStock.objects.filter(
            produit=self.panneau, type_mouvement=MouvementStock.TypeMouvement.ENTREE
        ).latest('id')
        self.assertEqual(mvt.quantite, 3)

    def test_retour_sans_restockage(self):
        api = self._api(self.resp)
        qte_avant = self.panneau.quantite_stock
        r = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': 'Produit détruit — non re-stockable',
                'restocker': False,
                'lignes': [{'produit': self.panneau.id, 'quantite': '2'}],
            }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        avoir = Avoir.objects.get(id=r.data['id'])
        self.assertFalse(avoir.restocke)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, qte_avant)

    def test_motif_obligatoire(self):
        api = self._api(self.resp)
        r = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': '',
                'restocker': True,
                'lignes': [{'produit': self.panneau.id, 'quantite': '1'}],
            }, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('motif', str(r.data).lower())

    def test_quantite_superieure_au_vendu_refusee(self):
        api = self._api(self.resp)
        r = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': 'Retour excessif',
                'restocker': True,
                'lignes': [{'produit': self.panneau.id, 'quantite': '11'}],
            }, format='json')
        self.assertEqual(r.status_code, 400)

    def test_pas_de_double_retour_au_dela_du_vendu(self):
        api = self._api(self.resp)
        r1 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': 'Premier retour',
                'restocker': True,
                'lignes': [{'produit': self.panneau.id, 'quantite': '7'}],
            }, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        # Il ne reste que 3 unités retournables (10 vendues - 7 déjà retournées).
        r2 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': 'Second retour excessif',
                'restocker': True,
                'lignes': [{'produit': self.panneau.id, 'quantite': '4'}],
            }, format='json')
        self.assertEqual(r2.status_code, 400)
        # Mais un second retour dans la limite restante passe.
        r3 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': 'Second retour correct',
                'restocker': True,
                'lignes': [{'produit': self.panneau.id, 'quantite': '3'}],
            }, format='json')
        self.assertEqual(r3.status_code, 201, r3.data)

    def test_cross_tenant_isolation_404(self):
        other = make_company('xpos7-other', 'Other XPOS7 Co')
        from apps.roles.models import Role, RESPONSABLE_PERMISSIONS
        other_role = Role.objects.create(
            company=other, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        other_user = User.objects.create_user(
            username='xpos7_other', password='x', role=other_role,
            role_legacy='responsable', company=other)
        api = self._api(other_user)
        r = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/retour-client/',
            {
                'motif': 'x',
                'restocker': True,
                'lignes': [{'produit': self.panneau.id, 'quantite': '1'}],
            }, format='json')
        self.assertEqual(r.status_code, 404)
