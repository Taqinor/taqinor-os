"""SCA23 — test « jour-2 » du tenant #2 : la porte de sellability en CI.

Chaque trou du groupe SCA (branding en dur, seeds vides, fallbacks fuyants) a
été découvert À LA MAIN ; rien ne garde le parcours d'un nouveau tenant dans la
durée. Ce module fait vivre ce parcours de bout en bout, et ÉCHOUE si un seed
hook (SCA20/SCA28) ou un fallback de branding (SCA25/26/27) régresse.

Découpage (guidance SCA23) :

  * ``Day2TenantJourneyTest`` — palier de suite STANDARD (exécuté au merge gate).
    ``register-company`` → login JWT → catalogue non-vide (SCA20) → remplir le
    ``CompanyProfile`` (étape jour-2 réaliste) → créer client + devis via l'API →
    assertions de BRANDING sur les CORPS D'EMAIL (SCA25 : « L'équipe {tenant} »,
    jamais « TAQINOR ») + assertions d'ISOLATION multi-tenant (le tenant #1 ne
    voit rien du tenant #2, et réciproquement).

  * ``Day2TenantProposalPdfTest`` (``@tag('pdf')``) — le rendu RÉEL du PDF
    ``/proposal`` (WeasyPrint lourd, exclu du merge gate, joué au palier release
    + par l'orchestrateur). Assertions : zéro fuite de la LIGNE DE CONTACT
    fondateur (``contact@taqinor.com`` / ``<b>TAQINOR</b>``) dans le pied de page
    d'un tenant qui a rempli son profil (SCA26/27), zéro ``taqinor.ma`` du tout
    quand le tenant a AUSSI rempli son site (SCA27 complément : ligne site +
    liens fiches câblés sur son site), et zéro ``prix_achat``.

  * ``Day2FooterNomOnlyFallbackTest`` (``SimpleTestCase``, pur) — DOCUMENTE la
    sémantique DC1 « nom seul » (un tenant qui ne renseigne QUE son nom garde la
    ligne de contact fondateur), pour qu'un changement futur soit DÉLIBÉRÉ.

Le test ne fait qu'APPELER ``/proposal`` (règle #4) — il ne touche jamais le
moteur, ni les statuts de document.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, override_settings, tag
from rest_framework.test import APIClient


# ── Constantes de branding fondateur à ne JAMAIS voir chez un tenant #2 ───────
FOUNDER_MARKERS = ('TAQINOR', 'taqinor', 'contact@taqinor')


def _register_company(api, *, nom, username, email):
    """register-company (public) → renvoie la réponse DRF."""
    return api.post('/api/django/auth/register-company/', {
        'company_nom': nom, 'username': username,
        'password': 'motdepasse123', 'email': email,
    }, format='json')


def _login_token(api, username, password='motdepasse123'):
    """login JWT (token/) → renvoie l'access token (str).

    ``CustomTokenObtainPairView`` déplace l'access token du corps de la réponse
    vers un cookie httpOnly ``access_token`` (contrat existant, sécurité) : on
    lit donc le cookie, pas ``r.data['access']`` (absent du corps)."""
    r = api.post('/api/django/token/', {
        'username': username, 'password': password}, format='json')
    assert r.status_code == 200, r.data
    return r.cookies['access_token'].value


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class Day2TenantJourneyTest(TestCase):
    """Parcours jour-2 complet d'un tenant #2, palier de suite standard."""

    def _create_client(self, api, *, nom, email):
        r = api.post('/api/django/crm/clients/', {
            'nom': nom, 'email': email,
            'telephone': '+212611000000', 'adresse': 'Casablanca',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def _create_devis_with_line(self, api, client_id, *, company):
        # Devis vide (référence auto-générée server-side, référence SCA/QW).
        r = api.post('/api/django/ventes/devis/', {
            'client': client_id, 'statut': 'brouillon',
            'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        devis_id = r.data['id']
        # Une ligne panneau (donne une puissance au moteur résidentiel).
        from apps.stock.models import Produit
        produit = Produit.objects.create(
            company=company, nom='Panneau mono 550W', sku='DAY2-PAN-550',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=100)
        lr = api.post('/api/django/ventes/devis-lignes/', {
            'devis': devis_id, 'produit': produit.id,
            'designation': 'Panneau mono 550W', 'quantite': '14',
            'prix_unitaire': '1100', 'remise': '0',
        }, format='json')
        self.assertEqual(lr.status_code, 201, lr.data)
        return devis_id

    def test_day2_journey_no_founder_branding_and_isolation(self):
        # 1) register-company (tenant #2 « ACME Énergie »).
        api = APIClient()
        r = _register_company(
            api, nom='ACME Énergie', username='acme-boss',
            email='boss@acme.ma')
        self.assertEqual(r.status_code, 201, r.data)
        from authentication.models import Company
        acme = Company.objects.get(nom='ACME Énergie')

        # 2) login JWT.
        token = _login_token(APIClient(), 'acme-boss')
        auth = APIClient()
        auth.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 3) catalogue non-vide (SCA20 : le hook signup a seedé le catalogue).
        from apps.stock.models import Produit
        self.assertGreater(
            Produit.objects.filter(company=acme).count(), 0,
            'le hook signup SCA20 doit seeder le catalogue du nouveau tenant')

        # 3bis) SCA28 : thème neutre + signature brandée seedés au signup.
        from core.models import BrandedTemplate, TenantTheme
        from core.selectors import EMAIL_SIGNATURE_CODE
        self.assertTrue(TenantTheme.objects.filter(company=acme).exists())
        self.assertTrue(BrandedTemplate.objects.filter(
            company=acme, kind=BrandedTemplate.KIND_EMAIL,
            code=EMAIL_SIGNATURE_CODE).exists())

        # 4) étape jour-2 réaliste : le tenant remplit SON CompanyProfile
        #    (nom + email + téléphone) — pilote emails ET pied de page PDF.
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.get(company=acme)
        profile.nom = 'ACME Énergie'
        profile.email = 'hello@acme.ma'
        profile.telephone = '+212 5 22 11 22 33'
        profile.save()

        # 5) créer client + devis via l'API (scopés au tenant server-side).
        client_id = self._create_client(
            auth, nom='Bennani', email='client@acme.ma')
        devis_id = self._create_devis_with_line(auth, client_id, company=acme)

        # 6) branding des CORPS D'EMAIL (SCA25) : signature = « L'équipe ACME
        #    Énergie », jamais « TAQINOR ». On passe par le service d'email réel
        #    (backend locmem → aucun envoi réseau) et on inspecte EmailLog.corps.
        from apps.ventes import email_service
        from apps.ventes.models import Devis, EmailLog
        devis = Devis.objects.get(pk=devis_id)
        boss = _tenant_admin(acme, 'acme-boss')
        email_service.send_document_email(devis, user=boss)
        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertIn("L'équipe ACME Énergie", log.corps)
        for marker in FOUNDER_MARKERS:
            self.assertNotIn(marker, log.corps,
                             f'fuite de branding fondateur « {marker} » '
                             f'dans le corps d\'email du tenant')

        # 6bis) EmailTemplate.render (SCA25) — le placeholder {entreprise} porte
        #       le nom du tenant, jamais le littéral fondateur.
        from apps.parametres.models_email import EmailTemplate
        rendered = EmailTemplate.render(
            acme, 'devis', civilite='M.', nom='Bennani',
            reference=devis.reference, lien='https://acme.ma/p')
        self.assertIn('ACME Énergie', rendered['corps'])
        self.assertNotIn('TAQINOR', rendered['corps'])
        self.assertNotIn('Taqinor', rendered['corps'])

        # 7) ISOLATION : un tenant #1 distinct ne voit RIEN du tenant #2.
        api2 = APIClient()
        r2 = _register_company(
            api2, nom='Autre Solaire', username='autre-boss',
            email='boss@autre.ma')
        self.assertEqual(r2.status_code, 201, r2.data)
        other_token = _login_token(APIClient(), 'autre-boss')
        other = APIClient()
        other.credentials(HTTP_AUTHORIZATION=f'Bearer {other_token}')

        # Le tenant #1 ne voit ni le client ni le devis du tenant #2.
        rc = other.get('/api/django/crm/clients/')
        self.assertEqual(rc.status_code, 200)
        ids = {c['id'] for c in _results(rc.data)}
        self.assertNotIn(client_id, ids)

        rd = other.get(f'/api/django/ventes/devis/{devis_id}/')
        self.assertIn(rd.status_code, (403, 404),
                      'le devis du tenant #2 doit être invisible au tenant #1')

        # Réciproquement, le tenant #2 voit bien SON devis.
        rd_own = auth.get(f'/api/django/ventes/devis/{devis_id}/')
        self.assertEqual(rd_own.status_code, 200, rd_own.data)


@tag('pdf')
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class Day2TenantProposalPdfTest(TestCase):
    """SCA23 (palier PDF) — le PDF /proposal RÉEL d'un tenant #2 ne fuit pas la
    ligne de contact fondateur (SCA26/27) et jamais un prix d'achat.

    Rendu WeasyPrint lourd → ``@tag('pdf')`` (exclu du merge gate ; joué au
    palier release + orchestrateur). MinIO mocké : les octets PDF sont RÉELS.
    """

    def _extract_text(self, pdf_bytes):
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        try:
            return '\n'.join(page.get_text() for page in doc)
        finally:
            doc.close()

    def _build_tenant_devis(self):
        """Register un tenant #2, remplit son profil, crée un devis résidentiel
        complet et renvoie ``(company, admin_user, devis_id, api)``."""
        api = APIClient()
        r = _register_company(
            api, nom='Helios SARL', username='helios-boss',
            email='boss@helios.ma')
        assert r.status_code == 201, r.data
        from authentication.models import Company
        company = Company.objects.get(nom='Helios SARL')

        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.get(company=company)
        profile.nom = 'Helios SARL'
        profile.email = 'hello@helios.ma'
        profile.telephone = '+212 5 22 00 00 00'
        # SCA27 (complément) — le tenant remplit AUSSI son site : le PDF ne doit
        # alors plus contenir AUCUNE trace de taqinor.ma (ligne site + fiches).
        profile.site_web = 'helios.ma'
        profile.save()

        token = _login_token(APIClient(), 'helios-boss')
        auth = APIClient()
        auth.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        rc = auth.post('/api/django/crm/clients/', {
            'nom': 'Meryem', 'email': 'meryem@example.com',
            'telephone': '+212600000000', 'adresse': 'Rabat',
        }, format='json')
        assert rc.status_code == 201, rc.data
        client_id = rc.data['id']

        rd = auth.post('/api/django/ventes/devis/', {
            'client': client_id, 'statut': 'brouillon',
            'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        assert rd.status_code == 201, rd.data
        devis_id = rd.data['id']

        from apps.stock.models import Produit
        # Forme résidentielle « deux options » PROUVÉE (cf. quote_engine tests) :
        # 14 panneaux + les deux onduleurs + batterie → le renderer résidentiel
        # (neutralisé SCA26/27) rend, plutôt que le legacy. Prix d'achat 9876
        # volontairement distinctif (ne doit JAMAIS fuiter dans le PDF).
        lines = [
            ('Onduleur réseau 10kW', 'HEL-OND-R', '11700', '5000', '1'),
            ('Onduleur hybride 5kW', 'HEL-OND-H', '24000', '5000', '1'),
            ('Panneau mono 550W', 'HEL-PAN-550', '1100', '9876', '14'),
            ('Batterie 5 kWh', 'HEL-BAT', '14000', '5000', '1'),
            ('Structures acier', 'HEL-STR', '375', '100', '14'),
            ('Socles', 'HEL-SOC', '67', '10', '30'),
            ('Accessoires', 'HEL-ACC', '1667', '100', '1'),
            ('Tableau De Protection AC/DC', 'HEL-TAB', '1667', '100', '1'),
            ('Installation', 'HEL-INST', '4000', '0', '1'),
            ('Transport', 'HEL-TRA', '1000', '0', '1'),
        ]
        for nom, sku, pv, pa, qty in lines:
            produit = Produit.objects.create(
                company=company, nom=nom, sku=sku,
                prix_vente=Decimal(pv), prix_achat=Decimal(pa),
                quantite_stock=100)
            lr = auth.post('/api/django/ventes/devis-lignes/', {
                'devis': devis_id, 'produit': produit.id,
                'designation': nom, 'quantite': qty,
                'prix_unitaire': pv, 'remise': '0',
            }, format='json')
            assert lr.status_code == 201, lr.data
        return company, devis_id, auth

    @patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket')
    @patch('apps.ventes.utils.pdf.download_pdf')
    @patch('apps.ventes.utils.pdf._upload_pdf')
    def test_proposal_pdf_no_founder_contact_line_no_buy_price(
            self, mock_upload, mock_download, _mock_bucket):
        company, devis_id, auth = self._build_tenant_devis()

        # /proposal upload → capture les octets ; download renvoie les mêmes.
        captured = {}

        def _capture_upload(pdf_bytes, key, *a, **k):
            captured['bytes'] = pdf_bytes
            return key
        mock_upload.side_effect = _capture_upload
        mock_download.side_effect = lambda key: captured['bytes']

        # APPEL /proposal (règle #4 : on RÉ-appelle uniquement, jamais modifier).
        resp = auth.get(f'/api/django/ventes/devis/{devis_id}/proposal/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        pdf_bytes = resp.content
        self.assertEqual(pdf_bytes[:4], b'%PDF')

        text = self._extract_text(pdf_bytes)

        # Ligne de contact fondateur ABSENTE (SCA26/27 — profil rempli) : le
        # pied de page « email · téléphone » est piloté par CompanyProfile.
        self.assertNotIn('contact@taqinor.com', text)
        # Coordonnées du tenant PRÉSENTES (preuve que le profil pilote le PDF).
        self.assertIn('hello@helios.ma', text)
        # Aucun prix d'achat revendeur ne fuit (jamais un centime — CLAUDE.md).
        self.assertNotIn('9876', text)
        self.assertNotIn('9 876', text)
        # Le nom du tenant apparaît (pied de page marque).
        self.assertIn('Helios SARL', text)

        # PORTÉE (SCA27 complément — câblage tenant site_url désormais fait) : le
        # tenant a rempli SON site (helios.ma), donc ``build_quote_data`` câble
        # ``site_url``/``links`` sur son site et le renderer résidentiel n'utilise
        # plus AUCUN littéral ``taqinor.ma`` (ligne site du pied de page + liens
        # fiches). On peut donc interdire ``taqinor.ma`` outright (la fuite
        # PRÉEXISTANTE de SCA23 est fermée). SON site est présent en preuve.
        self.assertIn('helios.ma', text)
        self.assertNotIn('taqinor.ma', text)


class Day2FooterNomOnlyFallbackTest(SimpleTestCase):
    """SCA23 (doc) — sémantique DC1 « nom seul » du pied de page résidentiel.

    DÉCISION connue (guidance SCA23) : un tenant qui ne renseigne QUE son nom
    (sans email/téléphone) garde la ligne de contact FONDATEUR — c'est la
    sémantique par-champ de ``theme._footer_brand`` / DC1 ``_apply_entreprise``.
    On l'ACTE ici (pas de DB, fonction pure) pour qu'un changement futur soit
    délibéré et non une régression silencieuse : le parcours jour-2 remplit donc
    email+téléphone AVANT d'exiger « zéro contact fondateur » sur le PDF.
    """

    def test_footer_nom_only_keeps_founder_contact_line(self):
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer(
            {'ref': 'DEV-DAY2', 'entreprise': {'nom': 'ACME Énergie'}})
        # Nom du tenant présent…
        self.assertIn('<b>ACME Énergie</b>', foot)
        # …mais la ligne de contact reste celle du fondateur (DC1, par champ).
        self.assertIn('contact@taqinor.com', foot)
        self.assertIn('+212 6 61 85 04 10', foot)

    def test_footer_full_identity_replaces_founder_contact(self):
        """Nom + email + téléphone → coordonnées tenant, zéro trace fondateur."""
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer({'ref': 'DEV-DAY2', 'entreprise': {
            'nom': 'ACME Énergie', 'email': 'hello@acme.ma',
            'telephone': '+212 5 22 11 22 33'}})
        self.assertIn('hello@acme.ma', foot)
        self.assertNotIn('contact@taqinor.com', foot)
        self.assertNotIn('TAQINOR', foot)


def _results(data):
    """Extrait la liste de résultats d'une réponse liste (paginée ou non)."""
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _tenant_admin(company, username):
    from authentication.models import CustomUser
    return CustomUser.objects.get(username=username, company=company)
