"""N20 — Tests des étiquettes QR/CODE128 + résolveur de scan.

Couvre :
  - rendu QR (matrice + SVG) et CODE128 (SVG) sans dépendance externe ;
  - planche d'étiquettes HTML + PDF (via WeasyPrint déjà présent) ;
  - action `etiquettes` (sortie html / pdf, symbology qr / code128) ;
  - résolveur `resolve` : PRODUIT:<id> → produit, SYSTEME:<id> → installation ;
  - scoping société strict (jamais d'accès cross-tenant) ;
  - ABSENCE du prix d'achat / marge dans toute sortie d'étiquette ;
  - LECTURE SEULE : la résolution d'un système ne modifie aucune installation.

Run :
    python manage.py test apps.stock.test_labels -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import labels
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug, nom='Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


# ── Encodeur autonome (pas de DB) ───────────────────────────────────────────

class TestEncoders(TestCase):
    def test_qr_matrix_is_square_and_bool(self):
        m = labels.qr_matrix('PRODUIT:1234')
        self.assertTrue(len(m) > 0)
        self.assertEqual(len(m), len(m[0]))            # carrée
        self.assertTrue(all(isinstance(v, bool) for row in m for v in row))

    def test_qr_matrix_finder_patterns_present(self):
        # Les trois finders (7x7) garantissent une structure QR valide.
        m = labels.qr_matrix('PRODUIT:1')
        size = len(m)
        # Coin haut-gauche : module sombre du finder.
        self.assertTrue(m[0][0])
        self.assertTrue(m[0][size - 1])
        self.assertTrue(m[size - 1][0])

    def test_qr_svg_is_inline_svg(self):
        svg = labels.qr_svg('SYSTEME:9')
        self.assertIn('<svg', svg)
        self.assertIn('</svg>', svg)
        self.assertIn('<rect', svg)

    def test_code128_svg_is_inline_svg(self):
        svg = labels.code128b_svg('PRODUIT:42')
        self.assertIn('<svg', svg)
        self.assertIn('<rect', svg)

    def test_tokens_helpers(self):
        self.assertEqual(labels.produit_token(7), 'PRODUIT:7')
        self.assertEqual(labels.systeme_token(3), 'SYSTEME:3')

    def test_render_labels_html_qr_and_code128(self):
        items = [{'token': 'PRODUIT:1', 'titre': 'Panneau 550W', 'sous_titre': 'PAN550'}]
        html_qr = labels.render_labels_html(items, symbology='qr')
        html_c128 = labels.render_labels_html(items, symbology='code128')
        for html in (html_qr, html_c128):
            self.assertIn('<!DOCTYPE html>', html)
            self.assertIn('Panneau 550W', html)
            self.assertIn('PAN550', html)
            self.assertIn('PRODUIT:1', html)
            self.assertIn('<svg', html)

    def test_render_labels_html_escapes(self):
        items = [{'token': 'PRODUIT:1', 'titre': 'A & <B>', 'sous_titre': 'x'}]
        html = labels.render_labels_html(items)
        self.assertIn('A &amp; &lt;B&gt;', html)
        self.assertNotIn('<B>', html)


# ── Action étiquettes + résolveur (DB + API) ────────────────────────────────

class LabelsApiBase(TestCase):
    def setUp(self):
        self.company = make_company('lbl-co', 'Labels Co')
        self.other = make_company('lbl-other', 'Other Co')
        self.user = User.objects.create_user(
            username='lbl_user', password='x', role_legacy='admin',
            company=self.company)
        self.other_user = User.objects.create_user(
            username='lbl_other', password='x', role_legacy='admin',
            company=self.other)
        self.p1 = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN550',
            prix_achat=Decimal('123.45'), prix_vente=Decimal('200'),
            quantite_stock=10)
        self.p2 = Produit.objects.create(
            company=self.company, nom='Onduleur 10kW', sku='OND10',
            prix_achat=Decimal('999.99'), prix_vente=Decimal('1500'),
            quantite_stock=5)
        self.foreign = Produit.objects.create(
            company=self.other, nom='Produit étranger', sku='FOR1',
            prix_achat=Decimal('50'), prix_vente=Decimal('80'),
            quantite_stock=1)
        self.api = auth(self.user)


class TestEtiquettesAction(LabelsApiBase):
    def test_html_output_lists_selected(self):
        res = self.api.get(
            f'/api/django/stock/produits/etiquettes/?ids={self.p1.id}'
            f'&ids={self.p2.id}&sortie=html')
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('Panneau 550W', body)
        self.assertIn('PAN550', body)
        self.assertIn('Onduleur 10kW', body)
        self.assertIn('PRODUIT:%d' % self.p1.id, body)

    def test_html_comma_separated_ids(self):
        res = self.api.get(
            f'/api/django/stock/produits/etiquettes/'
            f'?ids={self.p1.id},{self.p2.id}&sortie=html')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Panneau 550W', res.content.decode())
        self.assertIn('Onduleur 10kW', res.content.decode())

    def test_pdf_output_default(self):
        res = self.api.get(
            f'/api/django/stock/produits/etiquettes/?ids={self.p1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))

    def test_code128_symbology(self):
        res = self.api.get(
            f'/api/django/stock/produits/etiquettes/?ids={self.p1.id}'
            f'&symbology=code128&sortie=html')
        self.assertEqual(res.status_code, 200)
        self.assertIn('<svg', res.content.decode())

    def test_prix_achat_never_printed(self):
        # Le prix d'achat / marge ne doit JAMAIS fuiter sur l'étiquette.
        # (On compare des montants formatés ; un entier nu type « 200 » peut
        #  coïncider avec une coordonnée du SVG, donc on teste les décimales.)
        res = self.api.get(
            f'/api/django/stock/produits/etiquettes/?ids={self.p1.id}'
            f'&ids={self.p2.id}&sortie=html')
        body = res.content.decode()
        self.assertNotIn('123.45', body)        # prix_achat p1
        self.assertNotIn('999.99', body)        # prix_achat p2
        self.assertNotIn('prix_achat', body)
        # Le prix de vente non plus (étiquette = identification, pas tarif).
        self.assertNotIn('200.00', body)
        self.assertNotIn('1500.00', body)
        self.assertNotIn('prix_vente', body)
        # L'étiquette ne porte que nom + SKU + jeton.
        self.assertIn('PRODUIT:%d' % self.p1.id, body)
        self.assertIn('PAN550', body)

    def test_company_scoping_excludes_foreign_product(self):
        # Un id d'une autre société n'apparaît jamais ; ici seul un id étranger
        # est demandé → aucun produit correspondant → 404.
        res = self.api.get(
            f'/api/django/stock/produits/etiquettes/?ids={self.foreign.id}'
            f'&sortie=html')
        self.assertEqual(res.status_code, 404)

    def test_empty_ids_is_400(self):
        res = self.api.get('/api/django/stock/produits/etiquettes/?sortie=html')
        self.assertEqual(res.status_code, 400)


class TestResolve(LabelsApiBase):
    def test_resolve_produit(self):
        res = self.api.get(
            f'/api/django/stock/produits/resolve/'
            f'?code=PRODUIT:{self.p1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['type'], 'produit')
        self.assertEqual(res.data['id'], self.p1.id)
        self.assertEqual(res.data['label'], 'Panneau 550W')
        self.assertEqual(res.data['route'], '/stock')

    def test_resolve_produit_cross_tenant_is_404(self):
        # Le produit existe mais appartient à une autre société → introuvable.
        res = self.api.get(
            f'/api/django/stock/produits/resolve/'
            f'?code=PRODUIT:{self.foreign.id}')
        self.assertEqual(res.status_code, 404)

    def test_resolve_unknown_produit_is_404(self):
        res = self.api.get(
            '/api/django/stock/produits/resolve/?code=PRODUIT:999999')
        self.assertEqual(res.status_code, 404)

    def test_resolve_bad_code_is_400(self):
        # Codes vides ou malformés AVEC ':' (jeton interne mal formé) restent
        # 400. Un code SANS ':' (ex. 'garbage') est désormais tenté comme
        # code-barres fabricant (XSTK3) — voir test_resolve_bad_code_no_colon.
        for code in ('', 'PRODUIT:', 'PRODUIT:abc', ':12'):
            res = self.api.get(
                f'/api/django/stock/produits/resolve/?code={code}')
            self.assertIn(res.status_code, (400,), msg=f'code={code!r}')

    def test_resolve_bad_code_no_colon_is_404(self):
        # XSTK3 — un code sans ':' est tenté comme code-barres fabricant ;
        # sans correspondance, « produit introuvable » (404), jamais 400
        # (dégradation propre — un EAN inconnu n'est pas une erreur cliente).
        res = self.api.get(
            '/api/django/stock/produits/resolve/?code=garbage')
        self.assertEqual(res.status_code, 404)

    def test_resolve_unknown_prefix_is_400(self):
        res = self.api.get(
            '/api/django/stock/produits/resolve/?code=FACTURE:1')
        self.assertEqual(res.status_code, 400)

    def test_resolve_systeme_read_only(self):
        # Crée une installation minimale et vérifie résolution SANS écriture.
        from apps.crm.models import Client
        from apps.installations.models import Installation
        client = Client.objects.create(company=self.company, nom='Client X')
        inst = Installation.objects.create(
            company=self.company, reference='CH-2026-001', client=client,
            statut=Installation.Statut.SIGNE)
        before = Installation.objects.get(pk=inst.pk)
        before_updated = (before.date_modification
                          if hasattr(before, 'date_modification') else None)

        res = self.api.get(
            f'/api/django/stock/produits/resolve/?code=SYSTEME:{inst.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['type'], 'systeme')
        self.assertEqual(res.data['id'], inst.id)
        self.assertEqual(res.data['label'], 'CH-2026-001')
        self.assertEqual(res.data['route'], '/chantiers')
        self.assertEqual(res.data['client'], 'Client X')

        # Aucune mutation de l'installation : valeurs identiques après résolution.
        after = Installation.objects.get(pk=inst.pk)
        self.assertEqual(after.reference, 'CH-2026-001')
        self.assertEqual(after.statut, Installation.Statut.SIGNE)
        if before_updated is not None:
            self.assertEqual(after.date_modification, before_updated)

    def test_resolve_systeme_cross_tenant_is_404(self):
        from apps.crm.models import Client
        from apps.installations.models import Installation
        client = Client.objects.create(company=self.other, nom='Client Other')
        inst = Installation.objects.create(
            company=self.other, reference='CH-OTHER-1', client=client,
            statut=Installation.Statut.SIGNE)
        res = self.api.get(
            f'/api/django/stock/produits/resolve/?code=SYSTEME:{inst.id}')
        self.assertEqual(res.status_code, 404)

    def test_resolve_unknown_systeme_is_404(self):
        res = self.api.get(
            '/api/django/stock/produits/resolve/?code=SYSTEME:999999')
        self.assertEqual(res.status_code, 404)
