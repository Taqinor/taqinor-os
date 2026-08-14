"""NTWMS6 — unités logistiques : colis, palette, SSCC GS1.

Critère d'acceptation testé : une expédition de plusieurs palettes/colis a une
étiquette SSCC scannable PAR COLIS. On vérifie la conformité GS1 du code (18
chiffres + clé mod-10), l'unicité par société, la hiérarchie palette → colis,
et le gel du contenu au scellage.

Run :
    python manage.py test apps.stock.test_ntwms6_unite_logistique -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.gs1 import cle_controle_gs1, construire_sscc, sscc_valide
from apps.stock.models import Produit, UniteLogistique
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_unite_logistique,
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


class TestSsccGs1(TestCase):
    """La clé de contrôle est vérifiée contre l'EXEMPLE PUBLIÉ par GS1 —
    jamais contre notre propre calcul (ce qui ne prouverait rien)."""

    def test_exemple_officiel_gs1(self):
        self.assertTrue(sscc_valide('106141412345678908'))
        self.assertEqual(
            construire_sscc('0614141', '234567890', extension='1'),
            '106141412345678908')

    def test_cle_de_controle(self):
        self.assertEqual(cle_controle_gs1('10614141234567890'), 8)

    def test_code_invalide(self):
        self.assertFalse(sscc_valide('106141412345678900'))
        self.assertFalse(sscc_valide('12345'))
        self.assertFalse(sscc_valide('abcdefghijklmnopqr'))

    def test_entree_non_numerique_refusee(self):
        with self.assertRaises(ValueError):
            cle_controle_gs1('12A45')


class Ntwms6Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms6-co', 'NTWMS6 Co')
        self.autre = make_company('ntwms6-autre', 'NTWMS6 Autre')
        self.admin = User.objects.create_user(
            username='ntwms6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-NTWMS6',
            prix_achat=Decimal('90'), prix_vente=Decimal('140'),
            quantite_stock=50)
        self.api = auth(self.admin)


class TestUniteLogistique(Ntwms6Base):
    def test_creation_attribue_un_sscc_valide(self):
        colis = creer_unite_logistique(company=self.company)
        self.assertEqual(len(colis.sscc), 18)
        self.assertTrue(sscc_valide(colis.sscc))
        self.assertEqual(colis.statut,
                         UniteLogistique.Statut.EN_PREPARATION)

    def test_sscc_unique_et_croissant(self):
        premier = creer_unite_logistique(company=self.company)
        second = creer_unite_logistique(company=self.company)
        self.assertNotEqual(premier.sscc, second.sscc)
        self.assertTrue(sscc_valide(second.sscc))

    def test_sscc_ne_retrecit_pas_apres_suppression(self):
        """Anti-`count()+1` (collision constatée en production) : supprimer un
        colis du MILIEU ne doit jamais faire réattribuer un SSCC encore
        utilisé. La règle est « plus haut utilisé + 1 », comme
        `core.numbering`."""
        premier = creer_unite_logistique(company=self.company)
        milieu = creer_unite_logistique(company=self.company)
        dernier = creer_unite_logistique(company=self.company)
        milieu.delete()
        suivant = creer_unite_logistique(company=self.company)
        self.assertNotIn(suivant.sscc, {premier.sscc, dernier.sscc})
        self.assertTrue(sscc_valide(suivant.sscc))

    def test_palette_contient_des_colis(self):
        palette = creer_unite_logistique(
            company=self.company, type_unite='palette')
        colis = creer_unite_logistique(company=self.company, parent=palette)
        self.assertEqual(colis.parent_id, palette.id)
        self.assertEqual(palette.enfants.count(), 1)

    def test_un_colis_ne_peut_pas_contenir_une_unite(self):
        colis = creer_unite_logistique(company=self.company)
        with self.assertRaises(ValueError):
            creer_unite_logistique(company=self.company, parent=colis)

    def test_palette_d_une_autre_societe_refusee(self):
        palette_etrangere = creer_unite_logistique(
            company=self.autre, type_unite='palette')
        with self.assertRaises(ValueError):
            creer_unite_logistique(
                company=self.company, parent=palette_etrangere)


class TestScellage(Ntwms6Base):
    def test_unite_vide_non_scellable(self):
        colis = creer_unite_logistique(company=self.company)
        with self.assertRaises(ValueError):
            sceller_unite_logistique(unite=colis)

    def test_scellage_puis_contenu_fige(self):
        colis = creer_unite_logistique(company=self.company)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=colis, produit=self.produit,
            quantite=4)
        sceller_unite_logistique(unite=colis, user=self.admin)
        colis.refresh_from_db()
        self.assertEqual(colis.statut, UniteLogistique.Statut.SCELLE)
        self.assertIsNotNone(colis.date_scellage)
        with self.assertRaises(ValueError):
            ajouter_ligne_unite_logistique(
                company=self.company, unite=colis, produit=self.produit,
                quantite=1)

    def test_scellage_idempotent(self):
        colis = creer_unite_logistique(company=self.company)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=colis, produit=self.produit,
            quantite=1)
        sceller_unite_logistique(unite=colis, user=self.admin)
        premiere_date = UniteLogistique.objects.get(id=colis.id).date_scellage
        sceller_unite_logistique(
            unite=UniteLogistique.objects.get(id=colis.id), user=self.admin)
        self.assertEqual(
            UniteLogistique.objects.get(id=colis.id).date_scellage,
            premiere_date)

    def test_lignes_cumulees_pour_le_meme_produit(self):
        colis = creer_unite_logistique(company=self.company)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=colis, produit=self.produit,
            quantite=2)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=colis, produit=self.produit,
            quantite=3)
        self.assertEqual(colis.lignes.count(), 1)
        self.assertEqual(colis.lignes.first().quantite, 5)

    def test_produit_d_une_autre_societe_refuse(self):
        colis = creer_unite_logistique(company=self.company)
        etranger = Produit.objects.create(
            company=self.autre, nom='Intrus', sku='INT-NTWMS6',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        with self.assertRaises(ValueError):
            ajouter_ligne_unite_logistique(
                company=self.company, unite=colis, produit=etranger,
                quantite=1)


class TestEndpointsUniteLogistique(Ntwms6Base):
    def test_cycle_complet_par_api(self):
        resp = self.api.post('/api/django/stock/unites-logistiques/',
                             {'type_unite': 'colis'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(sscc_valide(resp.data['sscc']))
        unite_id = resp.data['id']

        resp = self.api.post(
            f'/api/django/stock/unites-logistiques/{unite_id}/lignes/',
            {'produit': self.produit.id, 'quantite': 6}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['lignes'][0]['quantite'], 6)

        resp = self.api.post(
            f'/api/django/stock/unites-logistiques/{unite_id}/sceller/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'scelle')
        self.assertTrue(resp.data['est_figee'])

    def test_sscc_jamais_accepte_du_client(self):
        resp = self.api.post('/api/django/stock/unites-logistiques/',
                             {'type_unite': 'colis',
                              'sscc': '999999999999999999'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.data['sscc'], '999999999999999999')

    def test_etiquette_html_contient_l_ai_00(self):
        colis = creer_unite_logistique(company=self.company)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=colis, produit=self.produit,
            quantite=2)
        resp = self.api.get(
            f'/api/django/stock/unites-logistiques/{colis.id}/etiquette-pdf/'
            '?sortie=html')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(f'(00){colis.sscc}', resp.content.decode('utf-8'))

    def test_isolation_societe(self):
        colis = creer_unite_logistique(company=self.company)
        intrus = User.objects.create_user(
            username='ntwms6_intrus', password='x', role_legacy='admin',
            company=self.autre)
        resp = auth(intrus).get(
            f'/api/django/stock/unites-logistiques/{colis.id}/')
        self.assertEqual(resp.status_code, 404)
