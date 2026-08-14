"""NTRET17 — étiquettes prix boutique (EAN-13) + réimpression en masse.

Critère d'acceptation testé : l'étiquette imprime un CODE-BARRES SCANNABLE
(EAN-13 valide) et le PRIX TTC courant ; la réimpression d'une CATÉGORIE
entière se fait en un appel.

L'EAN-13 est vérifié contre un code de référence publié (3760020507350) — la
clé de contrôle n'est jamais « supposée correcte ».

Run :
    python manage.py test apps.stock.test_ntret17_etiquette_prix -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.labels import (
    ean13_cle, ean13_normalise, ean13_svg, render_etiquettes_prix_html,
)
from apps.stock.models import Categorie, Produit

User = get_user_model()

URL = '/api/django/stock/produits/etiquettes-prix/'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntret17EanTests(TestCase):
    def test_la_cle_de_controle_est_conforme_a_un_code_publie(self):
        # 3760020507350 : clé 0 pour le préfixe 376002050735.
        self.assertEqual(ean13_cle('376002050735'), '0')

    def test_douze_chiffres_sont_completes_par_leur_cle(self):
        self.assertEqual(ean13_normalise('376002050735'), '3760020507350')

    def test_treize_chiffres_valides_passent_tels_quels(self):
        self.assertEqual(ean13_normalise('3760020507350'), '3760020507350')

    def test_un_code_a_cle_fausse_nest_jamais_repare_en_silence(self):
        self.assertEqual(ean13_normalise('3760020507359'), '')

    def test_un_code_de_longueur_invalide_est_rejete(self):
        for mauvais in ('', '123', 'ABCDEFGHIJKLM', '12345678901234'):
            self.assertEqual(ean13_normalise(mauvais), '')

    def test_le_svg_encode_les_95_modules_normalises(self):
        svg = ean13_svg('3760020507350', bar=2)
        self.assertTrue(svg.startswith('<svg'))
        # 3 + 6×7 + 5 + 6×7 + 3 = 95 modules.
        self.assertIn('width="190"', svg)
        self.assertIn('3760020507350', svg)

    def test_un_code_invalide_ne_produit_aucun_svg(self):
        self.assertEqual(ean13_svg('pas-un-code'), '')


class Ntret17PlancheTests(TestCase):
    def test_la_planche_porte_prix_ttc_et_code_barres(self):
        html = render_etiquettes_prix_html([{
            'nom': 'Disjoncteur 32 A', 'marque': 'Schneider',
            'sku': 'DJ32', 'code_barres': '3760020507350',
            'prix_ttc': Decimal('189.00'),
        }])
        self.assertIn('Disjoncteur 32 A', html)
        self.assertIn('189.00 DH', html)
        self.assertIn('<svg', html)
        self.assertIn('3760020507350', html)

    def test_un_produit_sans_code_barres_simprime_sans_code(self):
        html = render_etiquettes_prix_html([{
            'nom': 'Vis inox', 'sku': 'VIS', 'code_barres': '',
            'prix_ttc': Decimal('2.50'),
        }])
        self.assertIn('Vis inox', html)
        self.assertIn('2.50 DH', html)
        self.assertNotIn('<svg', html)

    def test_la_largeur_du_gabarit_est_configurable(self):
        html = render_etiquettes_prix_html([], largeur_mm=40)
        self.assertIn('width: 40mm', html)


class Ntret17EndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('ntret17-co', 'NTRET17 Co')
        self.autre = make_company('ntret17-autre', 'NTRET17 Autre')
        self.admin = User.objects.create_user(
            username='ntret17_admin', password='x', role_legacy='admin',
            company=self.company)
        self.rayon = Categorie.objects.create(
            company=self.company, nom='Rayon électricité NTRET17')
        self.autre_rayon = Categorie.objects.create(
            company=self.company, nom='Rayon plomberie NTRET17')
        for index in range(3):
            Produit.objects.create(
                company=self.company, nom=f'Article {index}',
                sku=f'ART{index}-NTRET17', categorie=self.rayon,
                # `(company, code_barres)` est UNIQUE : un code par article.
                # Prefixe distinct + cle recalculee -> 3 EAN-13 valides.
                code_barres=ean13_normalise(f'37600205073{index}'),
                prix_achat=Decimal('50'), prix_vente=Decimal('80'))
        Produit.objects.create(
            company=self.company, nom='Robinet', sku='ROB-NTRET17',
            categorie=self.autre_rayon, prix_achat=Decimal('30'),
            prix_vente=Decimal('55'))

    def test_reimpression_en_masse_dune_categorie_entiere(self):
        res = auth(self.admin).get(
            URL, {'categorie': self.rayon.id, 'sortie': 'html'})
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')
        self.assertEqual(html.count('class="etiquette"'), 3)
        self.assertNotIn('Robinet', html)

    def test_sans_selection_lappel_est_refuse(self):
        res = auth(self.admin).get(URL, {'sortie': 'html'})
        self.assertEqual(res.status_code, 400)

    def test_une_categorie_vide_renvoie_404(self):
        vide = Categorie.objects.create(
            company=self.company, nom='Rayon vide NTRET17')
        res = auth(self.admin).get(
            URL, {'categorie': vide.id, 'sortie': 'html'})
        self.assertEqual(res.status_code, 404)

    def test_le_prix_dachat_napparait_jamais_sur_letiquette(self):
        res = auth(self.admin).get(
            URL, {'categorie': self.rayon.id, 'sortie': 'html'})
        html = res.content.decode('utf-8')
        self.assertIn('80.00 DH', html)
        self.assertNotIn('50.00', html)

    def test_aucun_produit_dune_autre_societe(self):
        autre_categorie = Categorie.objects.create(
            company=self.autre, nom='Voisin NTRET17')
        Produit.objects.create(
            company=self.autre, nom='Produit voisin', sku='VOISIN-RET17',
            categorie=autre_categorie, prix_achat=Decimal('1'),
            prix_vente=Decimal('2'))
        res = auth(self.admin).get(
            URL, {'categorie': autre_categorie.id, 'sortie': 'html'})
        self.assertEqual(res.status_code, 404)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)


@tag('pdf')
class Ntret17PdfTests(Ntret17EndpointTests):
    """Rendu WeasyPrint RÉEL — hors palier rapide (étiquette `pdf`)."""

    def test_la_planche_pdf_est_servie(self):
        res = auth(self.admin).get(URL, {'categorie': self.rayon.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))
