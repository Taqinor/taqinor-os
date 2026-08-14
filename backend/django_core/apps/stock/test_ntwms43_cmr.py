"""NTWMS43 — export CMR / lettre de voiture d'une expédition.

Critère d'acceptation testé : générer une lettre de voiture pour une
expédition de 3 palettes affiche le POIDS TOTAL, le NOMBRE DE COLIS et les
RÉFÉRENCES SSCC.

Le rendu HTML est testé SANS WeasyPrint (fonction pure) ; le rendu PDF réel
est isolé dans une classe étiquetée ``@tag('pdf')`` pour rester hors du palier
rapide de la CI.

Run :
    python manage.py test apps.stock.test_ntwms43_cmr -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from apps.stock.models_wms import (
    ExpeditionTransporteur, UniteLogistique, UniteLogistiqueLigne,
)
from apps.stock.utils.pdf_cmr import build_cmr_context, render_cmr_html

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms43Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms43-co', 'NTWMS43 Co')
        self.autre = make_company('ntwms43-autre', 'NTWMS43 Autre')
        self.admin = User.objects.create_user(
            username='ntwms43_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550 Wc', sku='PAN-NTWMS43',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=100)

        # Une PALETTE mère + 2 palettes filles = 3 unités transportées.
        self.palette = UniteLogistique.objects.create(
            company=self.company, type_unite=UniteLogistique.TypeUnite.PALETTE,
            sscc='300000000000000018', poids_kg=Decimal('420.500'))
        self.fille_a = UniteLogistique.objects.create(
            company=self.company, type_unite=UniteLogistique.TypeUnite.PALETTE,
            sscc='300000000000000025', poids_kg=Decimal('380.000'),
            parent=self.palette)
        self.fille_b = UniteLogistique.objects.create(
            company=self.company, type_unite=UniteLogistique.TypeUnite.PALETTE,
            sscc='300000000000000032', poids_kg=Decimal('199.500'),
            parent=self.palette)
        UniteLogistiqueLigne.objects.create(
            company=self.company, unite=self.palette, produit=self.produit,
            quantite=30)
        UniteLogistiqueLigne.objects.create(
            company=self.company, unite=self.fille_a, produit=self.produit,
            quantite=28)

        self.expedition = ExpeditionTransporteur.objects.create(
            company=self.company, unite_logistique=self.palette,
            transporteur_provider=ExpeditionTransporteur.Provider.AMANA,
            numero_suivi='AMN-NTWMS43-001',
            destination='Agadir — Chantier Sud')


class Ntwms43ContexteTests(Ntwms43Base):
    def test_trois_palettes_donnent_poids_total_colis_et_sscc(self):
        ctx = build_cmr_context(self.expedition)

        self.assertEqual(ctx['nb_colis'], 3)
        self.assertEqual(ctx['poids_total_kg'], Decimal('1000.000'))
        self.assertEqual(sorted(ctx['sscc_liste']), [
            '300000000000000018', '300000000000000025', '300000000000000032'])

    def test_une_unite_sans_poids_compte_zero_jamais_un_poids_invente(self):
        self.fille_b.poids_kg = None
        self.fille_b.save(update_fields=['poids_kg'])
        ctx = build_cmr_context(self.expedition)
        self.assertEqual(ctx['poids_total_kg'], Decimal('800.500'))

    def test_le_transporteur_nomme_prime_sur_le_connecteur(self):
        ctx = build_cmr_context(self.expedition)
        self.assertEqual(ctx['transporteur'], 'Amana')


class Ntwms43HtmlTests(Ntwms43Base):
    def test_le_html_porte_les_trois_informations_exigees(self):
        html = render_cmr_html(self.expedition)

        self.assertIn('Nombre de colis : 3', html)
        self.assertIn('1000 kg', html)
        for sscc in ('300000000000000018', '300000000000000025',
                     '300000000000000032'):
            self.assertIn(sscc, html)
        self.assertIn('Agadir', html)

    def test_lexpediteur_est_la_societe_jamais_une_marque_en_dur(self):
        html = render_cmr_html(self.expedition)
        # White-label (SCA29) : ce document part chez un transporteur TIERS.
        self.assertNotIn('TAQINOR', html.upper())

    def test_une_expedition_sans_contenu_ne_casse_pas_le_rendu(self):
        UniteLogistiqueLigne.objects.all().delete()
        html = render_cmr_html(self.expedition)
        self.assertIn('Aucune ligne de contenu', html)


class Ntwms43EndpointTests(Ntwms43Base):
    def _url(self):
        return f'/api/django/stock/expeditions/{self.expedition.id}/cmr-pdf/'

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self._url()).status_code, 401)

    def test_une_expedition_dune_autre_societe_est_introuvable(self):
        autre_palette = UniteLogistique.objects.create(
            company=self.autre, sscc='300000000000000049')
        autre_exp = ExpeditionTransporteur.objects.create(
            company=self.autre, unite_logistique=autre_palette)
        res = auth(self.admin).get(
            f'/api/django/stock/expeditions/{autre_exp.id}/cmr-pdf/')
        self.assertEqual(res.status_code, 404)


@tag('pdf')
class Ntwms43PdfTests(Ntwms43Base):
    """Rendu WeasyPrint RÉEL — hors palier rapide (étiquette `pdf`)."""

    def test_le_pdf_est_genere_et_servi_inline(self):
        res = auth(self.admin).get(
            f'/api/django/stock/expeditions/{self.expedition.id}/cmr-pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))
        self.assertIn('lettre-de-voiture', res['Content-Disposition'])
