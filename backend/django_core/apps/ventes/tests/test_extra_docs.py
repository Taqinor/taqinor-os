"""Tests des documents clients premium ADDITIFS (N106) :

- trois lettres de relance à ton croissant (1 courtois / 2 ferme / 3 mise en
  demeure) — chacune un PDF valide avec son marqueur de ton ;
- fiche de remise / garantie après-vente — une page ;
- aucun prix d'achat / marge n'apparaît dans la sortie ;
- scoping société (un id d'une autre société renvoie 404).

Le moteur premium (``generate_devis_premium.py``) n'est jamais modifié : on
n'IMPORTE que ses helpers visuels.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneDevis, LigneFacture

User = get_user_model()

# Prix d'achat distinctif (jamais public) — on vérifie qu'il ne fuite JAMAIS.
SECRET_PRIX_ACHAT = Decimal('1337')


def make_company(slug='n106-co', nom='N106 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username='n106_user'):
    return User.objects.create_user(
        username=username, password='x', role_legacy='responsable',
        company=company)


def _is_pdf(blob):
    return isinstance(blob, (bytes, bytearray)) and blob[:5] == b'%PDF-'


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Sara',
            email='sara@example.com', telephone='+212600000001',
            adresse='12 Av. Hassan II, Casablanca')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur hybride', sku='OND-H-1',
            marque='Deye', garantie='Garantie 10 ans constructeur',
            prix_vente=Decimal('12000'), prix_achat=SECRET_PRIX_ACHAT,
            quantite_stock=10, tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-N106-0001',
            client=self.client_obj, statut='accepte',
            taux_tva=Decimal('20.00'), created_by=self.user)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation='Onduleur hybride 5 kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('12000'), remise=Decimal('0'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _facture(self):
        f = Facture.objects.create(
            company=self.company, reference='FAC-N106-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=40))
        LigneFacture.objects.create(
            facture=f, produit=self.produit, designation='Onduleur hybride',
            quantite=Decimal('1'), prix_unitaire=Decimal('12000'),
            taux_tva=Decimal('20.00'))
        return f

    def _chantier(self):
        return Installation.objects.create(
            company=self.company, reference='CH-N106-0001',
            client=self.client_obj, devis=self.devis,
            statut=Installation.Statut.RECEPTIONNE,
            puissance_installee_kwc=Decimal('6.50'),
            type_installation=Installation.TypeInstallation.RESIDENTIEL,
            raccordement=Installation.Raccordement.MONOPHASE,
            site_adresse='12 Av. Hassan II', site_ville='Casablanca',
            date_mise_en_service=date.today() - timedelta(days=5),
            date_reception=date.today(), technicien_responsable=self.user)


class TestLettreRelancePremium(_Base):
    def test_three_escalating_tones_render_valid_pdf(self):
        from apps.ventes.quote_engine.extra_docs import (
            RELANCE_TONES, render_lettre_relance_pdf)
        facture = self._facture()
        for niveau in (1, 2, 3):
            pdf = render_lettre_relance_pdf(facture, niveau)
            self.assertTrue(_is_pdf(pdf), f'niveau {niveau} not a PDF')
            self.assertGreater(len(pdf), 1000)
        # Les trois tons sont distincts (marqueurs uniques).
        markers = {RELANCE_TONES[n]['marker'] for n in (1, 2, 3)}
        self.assertEqual(len(markers), 3)
        self.assertEqual(RELANCE_TONES[1]['marker'], 'Relance amiable')
        self.assertEqual(RELANCE_TONES[2]['marker'], 'Relance ferme')
        self.assertEqual(RELANCE_TONES[3]['marker'], 'Mise en demeure')

    def test_tone_marker_present_in_html_per_level(self):
        from apps.ventes.quote_engine.extra_docs import (
            RELANCE_TONES, _facture_resume, build_lettre_relance_html)
        facture = self._facture()
        ctx = {'entreprise_nom': 'N106 Co'}
        client = {'nom': 'Bennani', 'prenom': 'Sara'}
        resume = _facture_resume(facture)
        for niveau in (1, 2, 3):
            html = build_lettre_relance_html(ctx, client, resume, niveau)
            self.assertIn(RELANCE_TONES[niveau]['marker'], html)
            self.assertIn(RELANCE_TONES[niveau]['title'], html)

    def test_no_prix_achat_leak(self):
        from apps.ventes.quote_engine.extra_docs import (
            render_lettre_relance_pdf)
        facture = self._facture()
        for niveau in (1, 2, 3):
            pdf = render_lettre_relance_pdf(facture, niveau)
            self.assertNotIn(b'1337', pdf)
            self.assertNotIn(b'prix_achat', pdf)

    def test_endpoint_levels_and_scope(self):
        facture = self._facture()
        for niveau in (1, 2, 3):
            resp = self.api.get(
                f'/api/django/ventes/factures/{facture.id}/'
                f'lettre-relance-premium/?niveau={niveau}')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp['Content-Type'], 'application/pdf')
        # Niveau invalide → 400.
        resp = self.api.get(
            f'/api/django/ventes/factures/{facture.id}/'
            'lettre-relance-premium/?niveau=9')
        self.assertEqual(resp.status_code, 400)
        # Autre société → 404.
        other_co = make_company(slug='other-co', nom='Other Co')
        other_user = make_user(other_co, username='other_user')
        api2 = APIClient()
        api2.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(other_user)}')
        resp = api2.get(
            f'/api/django/ventes/factures/{facture.id}/'
            'lettre-relance-premium/?niveau=1')
        self.assertEqual(resp.status_code, 404)


class TestFicheRemisePremium(_Base):
    def test_renders_single_page_pdf(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.extra_docs import (
            build_fiche_remise_html, render_fiche_remise_pdf,
            _chantier_composants)
        chantier = self._chantier()
        # Octets PDF valides.
        pdf = render_fiche_remise_pdf(chantier)
        self.assertTrue(_is_pdf(pdf))
        # Exactement UNE page (compté via WeasyPrint, comme test_quote_engine).
        ctx = {'entreprise_nom': 'N106 Co', 'entreprise_email': 'a@b.ma'}
        client = {'nom': 'Bennani', 'prenom': 'Sara'}
        info = {'reference': chantier.reference,
                'puissance_kwc': chantier.puissance_installee_kwc,
                'type_installation': 'Résidentiel'}
        html = build_fiche_remise_html(
            ctx, client, info, _chantier_composants(chantier))
        doc = HTML(string=html).render()
        self.assertEqual(
            len(doc.pages), 1,
            f'fiche de remise must be exactly 1 page, got {len(doc.pages)}')

    def test_garantie_present_no_prix_achat_leak(self):
        from apps.ventes.quote_engine.extra_docs import (
            build_fiche_remise_html, render_fiche_remise_pdf,
            _chantier_composants)
        chantier = self._chantier()
        ctx = {'entreprise_nom': 'N106 Co'}
        client = {'nom': 'Bennani', 'prenom': 'Sara'}
        composants = _chantier_composants(chantier)
        self.assertTrue(composants)
        self.assertEqual(composants[0]['garantie'],
                         'Garantie 10 ans constructeur')
        info = {'reference': chantier.reference,
                'puissance_kwc': chantier.puissance_installee_kwc}
        html = build_fiche_remise_html(ctx, client, info, composants)
        self.assertIn('Garantie 10 ans constructeur', html)
        self.assertNotIn('1337', html)
        self.assertNotIn('prix_achat', html)
        pdf = render_fiche_remise_pdf(chantier)
        self.assertNotIn(b'1337', pdf)
        self.assertNotIn(b'prix_achat', pdf)

    def test_endpoint_and_scope(self):
        chantier = self._chantier()
        resp = self.api.get(
            f'/api/django/ventes/chantiers/{chantier.id}/fiche-remise-premium/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        # Autre société → 404.
        other_co = make_company(slug='other-co-2', nom='Other Co 2')
        other_user = make_user(other_co, username='other_user_2')
        api2 = APIClient()
        api2.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(other_user)}')
        resp = api2.get(
            f'/api/django/ventes/chantiers/{chantier.id}/fiche-remise-premium/')
        self.assertEqual(resp.status_code, 404)
