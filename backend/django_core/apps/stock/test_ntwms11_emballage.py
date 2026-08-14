"""NTWMS11 — poste d'emballage avec contrôle de conformité BLOQUANT.

Critère d'acceptation testé : scanner un produit qui n'appartient pas à la
vague en cours d'emballage provoque un REFUS BLOQUANT avant la validation du
colis (400 côté API, `ValueError` côté service) — et rien n'est écrit.

Run :
    python manage.py test apps.stock.test_ntwms11_emballage -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit, UniteLogistiqueLigne
from apps.stock.services import (
    controler_scan_emballage, creer_unite_logistique,
    creer_vague_depuis_besoins, lancer_vague, prelever_ligne_picking,
    sceller_unite_logistique,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms11Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms11-co', 'NTWMS11 Co')
        self.autre = make_company('ntwms11-autre', 'NTWMS11 Autre')
        self.admin = User.objects.create_user(
            username='ntwms11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.attendu = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-NTWMS11',
            prix_achat=Decimal('90'), prix_vente=Decimal('140'),
            quantite_stock=50)
        self.intrus = Produit.objects.create(
            company=self.company, nom='Câble 10mm', sku='CAB-NTWMS11',
            prix_achat=Decimal('4'), prix_vente=Decimal('8'),
            quantite_stock=50)

        self.vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.attendu.id, 'quantite': 6}])
        lancer_vague(self.vague)
        ligne = self.vague.lignes.first()
        prelever_ligne_picking(ligne=ligne, quantite=6, user=self.admin)

        self.colis = creer_unite_logistique(
            company=self.company, vague=self.vague)
        self.api = auth(self.admin)


class TestControleConformite(Ntwms11Base):
    def test_produit_attendu_accepte_et_horodate(self):
        ligne = controler_scan_emballage(
            company=self.company, unite=self.colis, produit=self.attendu,
            quantite=2, user=self.admin)
        self.assertEqual(ligne.quantite, 2)
        self.assertIsNotNone(ligne.scanne_le)
        self.assertEqual(ligne.scanne_par_id, self.admin.id)

    def test_produit_hors_vague_refuse_et_rien_ecrit(self):
        with self.assertRaises(ValueError) as ctx:
            controler_scan_emballage(
                company=self.company, unite=self.colis, produit=self.intrus,
                quantite=1, user=self.admin)
        self.assertIn('vague', str(ctx.exception).lower())
        self.assertEqual(
            UniteLogistiqueLigne.objects.filter(unite=self.colis).count(), 0)

    def test_quantite_superieure_au_preleve_refusee(self):
        controler_scan_emballage(
            company=self.company, unite=self.colis, produit=self.attendu,
            quantite=6, user=self.admin)
        with self.assertRaises(ValueError):
            controler_scan_emballage(
                company=self.company, unite=self.colis,
                produit=self.attendu, quantite=1, user=self.admin)
        ligne = UniteLogistiqueLigne.objects.get(unite=self.colis)
        self.assertEqual(ligne.quantite, 6)

    def test_scans_successifs_cumules(self):
        controler_scan_emballage(
            company=self.company, unite=self.colis, produit=self.attendu,
            quantite=2, user=self.admin)
        controler_scan_emballage(
            company=self.company, unite=self.colis, produit=self.attendu,
            quantite=3, user=self.admin)
        self.assertEqual(
            UniteLogistiqueLigne.objects.get(unite=self.colis).quantite, 5)

    def test_unite_scellee_refusee(self):
        controler_scan_emballage(
            company=self.company, unite=self.colis, produit=self.attendu,
            quantite=1, user=self.admin)
        sceller_unite_logistique(unite=self.colis, user=self.admin)
        self.colis.refresh_from_db()
        with self.assertRaises(ValueError):
            controler_scan_emballage(
                company=self.company, unite=self.colis,
                produit=self.attendu, quantite=1, user=self.admin)

    def test_unite_sans_vague_accepte_tout(self):
        """Colisage LIBRE (sans vague) : aucun attendu à comparer, le contrôle
        se contente d'enregistrer — comportement historique préservé."""
        libre = creer_unite_logistique(company=self.company)
        ligne = controler_scan_emballage(
            company=self.company, unite=libre, produit=self.intrus,
            quantite=1, user=self.admin)
        self.assertEqual(ligne.quantite, 1)

    def test_produit_d_une_autre_societe_refuse(self):
        etranger = Produit.objects.create(
            company=self.autre, nom='Intrus', sku='INT-NTWMS11',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        with self.assertRaises(ValueError):
            controler_scan_emballage(
                company=self.company, unite=self.colis, produit=etranger,
                quantite=1, user=self.admin)

    def test_quantite_non_positive_refusee(self):
        with self.assertRaises(ValueError):
            controler_scan_emballage(
                company=self.company, unite=self.colis,
                produit=self.attendu, quantite=0, user=self.admin)


class TestEndpointControleScan(Ntwms11Base):
    def _url(self):
        return (f'/api/django/stock/unites-logistiques/{self.colis.id}/'
                'controler-scan/')

    def test_scan_conforme_201(self):
        resp = self.api.post(
            self._url(), {'produit': self.attendu.id, 'quantite': 2},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['lignes'][0]['quantite'], 2)
        self.assertIsNotNone(resp.data['lignes'][0]['scanne_le'])

    def test_scan_intrus_refus_bloquant_400(self):
        resp = self.api.post(
            self._url(), {'produit': self.intrus.id, 'quantite': 1},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('vague', str(resp.data).lower())
        self.assertEqual(
            UniteLogistiqueLigne.objects.filter(unite=self.colis).count(), 0)

    def test_isolation_societe(self):
        intrus_user = User.objects.create_user(
            username='ntwms11_intrus', password='x', role_legacy='admin',
            company=self.autre)
        resp = auth(intrus_user).post(
            self._url(), {'produit': self.attendu.id, 'quantite': 1},
            format='json')
        self.assertEqual(resp.status_code, 404)
