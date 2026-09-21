"""NTMFG33 — Permissions par rôle fines sur le module `mrp`
(technicien/responsable/admin).

Critère : un Technicien reçoit 403 sur `mrp/analyse-couts/` et
`mrp/parametres/`, un Responsable peut planifier mais pas modifier les
paramètres société, un Admin a accès complet ; tests par rôle."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class MatricePermissionsTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg33-1', 'MRP NTMFG33 1')
        self.technicien = make_user(self.company, 'mrp-ntmfg33-tech', role='normal')
        self.responsable = make_user(self.company, 'mrp-ntmfg33-resp', role='responsable')
        self.admin = make_user(self.company, 'mrp-ntmfg33-admin', role='admin')

        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-33', nom='Poste 33',
            capacite_heures_jour=Decimal('8'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme 33', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste, libelle='Découpe',
            temps_prepa_min=Decimal('5'), temps_unitaire_min=Decimal('1'))

    # ── Technicien : lecture OF + terminal atelier, RIEN d'autre ──────────

    def test_technicien_403_sur_analyse_couts(self):
        resp = auth(self.technicien).get('/api/django/mrp/analyse-couts/')
        self.assertEqual(resp.status_code, 403)

    def test_technicien_403_sur_parametres(self):
        resp = auth(self.technicien).get('/api/django/mrp/parametres/')
        self.assertEqual(resp.status_code, 403)

    def test_technicien_403_sur_confirmer_of(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5, gamme=self.gamme)
        resp = auth(self.technicien).post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/confirmer/')
        self.assertEqual(resp.status_code, 403)

    def test_technicien_peut_demarrer_pauser_terminer_sa_propre_operation(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5, gamme=self.gamme)
        resp = auth(self.responsable).post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/confirmer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        operation_id = resp.data['operations'][0]['id']

        api = auth(self.technicien)
        resp = api.post(f'/api/django/mrp/operations-of/{operation_id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = api.post(f'/api/django/mrp/operations-of/{operation_id}/pauser/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = api.post(f'/api/django/mrp/operations-of/{operation_id}/reprendre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = api.post(
            f'/api/django/mrp/operations-of/{operation_id}/terminer/',
            {'quantite_bonne': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    # ── Responsable : planification OF, PAS les paramètres ────────────────

    def test_responsable_peut_planifier_of(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5, gamme=self.gamme)
        resp = auth(self.responsable).post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/confirmer/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_responsable_403_sur_parametres(self):
        resp = auth(self.responsable).get('/api/django/mrp/parametres/')
        self.assertEqual(resp.status_code, 403)
        resp = auth(self.responsable).put(
            '/api/django/mrp/parametres/update/',
            {'horizon_mrp_jours': 5}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_responsable_peut_voir_analyse_couts(self):
        resp = auth(self.responsable).get('/api/django/mrp/analyse-couts/')
        self.assertEqual(resp.status_code, 200)

    # ── Admin : accès complet ──────────────────────────────────────────────

    def test_admin_acces_complet(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=5, gamme=self.gamme)
        api = auth(self.admin)
        resp = api.post(f'/api/django/mrp/ordres-fabrication/{of.id}/confirmer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = api.get('/api/django/mrp/analyse-couts/')
        self.assertEqual(resp.status_code, 200)
        resp = api.get('/api/django/mrp/parametres/')
        self.assertEqual(resp.status_code, 200)
        resp = api.put(
            '/api/django/mrp/parametres/update/',
            {'horizon_mrp_jours': 15}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
