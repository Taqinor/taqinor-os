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
from html import escape

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import (
    Devis, Facture, FollowupLevel, LigneDevis, LigneFacture)

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


@tag('pdf')  # toutes les sous-classes rendent des PDF (relances/fiches) → lourd
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


class TestLettreRelanceEscaladeNiveau(_Base):
    """L13 — le CORPS de la lettre escalade selon le ``FollowupLevel.message``
    du niveau (ton doux J+7 → ferme J+30), sans changer la mise en page premium.
    """

    def _seed_levels(self):
        """Trois niveaux à messages distincts (doux → ferme)."""
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel', delai_jours=7,
            message='Petit rappel tres courtois pour la facture {reference}.')
        FollowupLevel.objects.create(
            company=self.company, ordre=2, nom='Relance', delai_jours=15,
            message='Relance ferme : reglez la facture {reference} sans delai.')
        FollowupLevel.objects.create(
            company=self.company, ordre=3, nom='Mise en demeure',
            delai_jours=30,
            message='Mise en demeure formelle de payer la facture {reference}.')

    def test_distinct_body_per_level(self):
        """Niveau doux (1, J+7) et niveau ferme (3, J+30) produisent des corps
        de texte DIFFERENTS, repris du message du niveau correspondant."""
        from apps.ventes.quote_engine.extra_docs import (
            _facture_resume, build_lettre_relance_html, render_lettre_relance_pdf)
        self._seed_levels()
        facture = self._facture()
        resume = _facture_resume(facture)
        ctx = {'entreprise_nom': 'N106 Co'}
        client = {'nom': 'Bennani', 'prenom': 'Sara'}

        soft = build_lettre_relance_html(
            ctx, client, resume,
            niveau=1, message='Petit rappel tres courtois pour la facture '
                              '{reference}.')
        firm = build_lettre_relance_html(
            ctx, client, resume,
            niveau=3, message='Mise en demeure formelle de payer la facture '
                              '{reference}.')
        # Corps distincts, chacun reprenant SON message (gabarit {reference}
        # resolu avec la reference de la facture).
        self.assertIn('Petit rappel tres courtois', soft)
        self.assertNotIn('Petit rappel tres courtois', firm)
        self.assertIn('Mise en demeure formelle de payer', firm)
        self.assertNotIn('Mise en demeure formelle de payer', soft)
        self.assertIn(resume['reference'], soft)
        self.assertIn(resume['reference'], firm)
        self.assertNotEqual(soft, firm)

        # Le rendu PDF de bout en bout resout aussi le message du niveau
        # (J+7 doux vs J+30 ferme) et produit des octets PDF non vides.
        pdf_soft = render_lettre_relance_pdf(facture, 1)
        pdf_firm = render_lettre_relance_pdf(facture, 3)
        self.assertTrue(_is_pdf(pdf_soft))
        self.assertTrue(_is_pdf(pdf_firm))
        self.assertGreater(len(pdf_soft), 1000)
        self.assertGreater(len(pdf_firm), 1000)

    def test_default_body_when_no_level_message(self):
        """Sans message specifique (aucun niveau configure), le corps par
        defaut du ton est conserve — retro-compatibilite."""
        from apps.ventes.quote_engine.extra_docs import (
            RELANCE_TONES, _facture_resume, build_lettre_relance_html,
            render_lettre_relance_pdf)
        facture = self._facture()  # aucun FollowupLevel cree
        resume = _facture_resume(facture)
        ctx = {'entreprise_nom': 'N106 Co'}
        client = {'nom': 'Bennani', 'prenom': 'Sara'}
        for niveau in (1, 2, 3):
            default_html = build_lettre_relance_html(
                ctx, client, resume, niveau)
            via_none = build_lettre_relance_html(
                ctx, client, resume, niveau, message=None)
            via_empty = build_lettre_relance_html(
                ctx, client, resume, niveau, message='')
            # Le corps par defaut (premier paragraphe du ton) est present.
            first_para = RELANCE_TONES[niveau]['paras'][0]
            self.assertIn(escape(first_para)[:40], default_html)
            # message=None ou message='' == comportement historique.
            self.assertEqual(default_html, via_none)
            self.assertEqual(default_html, via_empty)
        # Le PDF se rend toujours (octets non vides) sans niveau configure.
        pdf = render_lettre_relance_pdf(facture, 1)
        self.assertTrue(_is_pdf(pdf))
        self.assertGreater(len(pdf), 1000)

    def test_layout_unchanged_only_body_text_varies(self):
        """La mise en page premium (squelette CSS/en-tete/pied) est identique
        entre le corps par defaut et le corps issu d'un message de niveau ;
        seul le texte des paragraphes change."""
        from apps.ventes.quote_engine.extra_docs import (
            _facture_resume, build_lettre_relance_html)
        facture = self._facture()
        resume = _facture_resume(facture)
        ctx = {'entreprise_nom': 'N106 Co'}
        client = {'nom': 'Bennani', 'prenom': 'Sara'}
        default_html = build_lettre_relance_html(ctx, client, resume, 1)
        custom_html = build_lettre_relance_html(
            ctx, client, resume, 1, message='Un corps de niveau entierement '
                                            'different du defaut.')
        # Le squelette de mise en page (classes premium) est present a
        # l'identique dans les deux variantes.
        for marker in ('<div class="page">', 'class="hdr"', 'class="body"',
                       'class="ftr"', 'class="callout"', 'class="title serif"',
                       'class="sign"'):
            self.assertIn(marker, default_html)
            self.assertIn(marker, custom_html)
        # Seul le texte du corps differe.
        self.assertIn('Un corps de niveau entierement', custom_html)
        self.assertNotIn('Un corps de niveau entierement', default_html)


class TestLogoBlockNeutralFallback(TestCase):
    """SCA26 — sans logo société, l'en-tête ne retombe PLUS sur le logo premium
    TAQINOR (fuite de marque cross-tenant) mais sur un bloc NEUTRE (nom stylé) ou
    rien. Fonction pure sur un dict ctx : aucun rendu PDF, aucune DB."""

    def test_uploaded_logo_uri_renders_img(self):
        from apps.ventes.quote_engine.extra_docs import _logo_block
        out = _logo_block({'logo_uri': 'data:image/png;base64,AAAA',
                           'entreprise_nom': 'Autre Tenant'})
        self.assertIn('<img', out)
        self.assertIn('data:image/png;base64,AAAA', out)
        # Le nom stylé n'est PAS utilisé quand un logo existe.
        self.assertNotIn('font-weight:800', out)

    def test_no_logo_uses_neutral_company_name_not_taqinor(self):
        from apps.ventes.quote_engine.extra_docs import _logo_block
        out = _logo_block({'logo_uri': None, 'entreprise_nom': 'Autre Tenant'})
        # Bloc neutre = nom société stylé, JAMAIS le logo premium TAQINOR.
        self.assertIn('Autre Tenant', out)
        self.assertNotIn('alt="TAQINOR"', out)
        self.assertNotIn('TAQIN', out)
        self.assertNotIn('<img', out)

    def test_no_logo_no_name_renders_nothing(self):
        from apps.ventes.quote_engine.extra_docs import _logo_block
        self.assertEqual(_logo_block({'logo_uri': None}), '')
        self.assertEqual(_logo_block({'logo_uri': None,
                                      'entreprise_nom': '   '}), '')

    def test_company_name_is_html_escaped(self):
        from apps.ventes.quote_engine.extra_docs import _logo_block
        out = _logo_block({'entreprise_nom': 'A & B <Solar>'})
        self.assertIn('A &amp; B &lt;Solar&gt;', out)
        self.assertNotIn('<Solar>', out)

    def test_neutral_block_never_emits_premium_taqinor_logo(self):
        """Un tenant sans logo n'obtient jamais l'``alt="TAQINOR"`` du moteur."""
        from apps.ventes.quote_engine.extra_docs import _logo_block
        for nom in ('Helios Énergie', 'ACME', ''):
            out = _logo_block({'logo_uri': None, 'entreprise_nom': nom})
            self.assertNotIn('TAQINOR', out)


@tag('pdf')
class TestLogoNeutralFallbackRendered(_Base):
    """SCA26 (harnais rendu) — une lettre de relance d'un tenant SANS logo
    société rend son nom neutre et n'imprime jamais le logo premium TAQINOR."""

    def test_lettre_relance_html_neutral_header_for_logoless_tenant(self):
        from apps.ventes.quote_engine.extra_docs import (
            _facture_resume, build_lettre_relance_html)
        facture = self._facture()
        # ctx d'un tenant sans logo (logo_uri absent) mais avec son nom.
        ctx = {'entreprise_nom': 'Helios Énergie'}
        client = {'nom': 'Bennani', 'prenom': 'Sara'}
        resume = _facture_resume(facture)
        html = build_lettre_relance_html(ctx, client, resume, 1)
        self.assertIn('Helios', html)
        # Aucun logo premium TAQINOR dans l'en-tête.
        self.assertNotIn('alt="TAQINOR"', html)


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
