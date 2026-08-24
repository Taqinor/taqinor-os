"""Group Q — Devis ↔ Toiture 3D pipeline (Q1 layout storage, Q4 roof image,
Q6 tokenized proposal data, Q7 e-signature acceptance).

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_roof_pipeline -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x',
        role_legacy='responsable', company=company)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_devis(company, ref='DEV-ROOF-0001', with_lines=True):
    client = Client.objects.create(
        company=company, nom='Toiti', prenom='Cli',
        email=f'{ref}@ex.com', telephone='+212600000000',
        adresse='Anfa, Casablanca')
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'))
    if with_lines:
        for desig, qty, pu in [
            ('Panneau mono 550W', '12', '1100'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Structures acier', '12', '375'),
        ]:
            p = Produit_create(company, desig, pu)
            LigneDevis.objects.create(
                devis=devis, produit=p, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
    return devis


def Produit_create(company, nom, pu):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, sku=f'{nom[:8]}-{company.pk}',
        prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=50)


SAMPLE_LAYOUT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitch': 10,
        'azimuth': 180,
    }],
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
    'renderPlan': {'cells': 12},
}


class TestQ1Layout(TestCase):
    def setUp(self):
        self.company = make_company('q1-co')
        self.api = auth_client(make_user(self.company, 'q1user'))
        self.devis = make_devis(self.company)

    def test_save_then_load_round_trip(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        resp = self.api.post(url, SAMPLE_LAYOUT, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.roof_layout['result']['kwc'], 6.6)
        got = self.api.get(url)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.data['roof_layout'], SAMPLE_LAYOUT)

    def test_wrapper_form_accepted(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        resp = self.api.post(url, {'roof_layout': SAMPLE_LAYOUT}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.roof_layout, SAMPLE_LAYOUT)

    def test_status_unchanged(self):
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        self.api.post(url, SAMPLE_LAYOUT, format='json')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')

    def test_cross_tenant_404(self):
        other = make_company('q1-other')
        other_api = auth_client(make_user(other, 'q1other'))
        url = f'/api/django/ventes/devis/{self.devis.id}/layout/'
        self.assertEqual(other_api.post(url, SAMPLE_LAYOUT, format='json')
                         .status_code, 404)
        self.assertEqual(other_api.get(url).status_code, 404)


class TestQ4RoofImage(TestCase):
    def setUp(self):
        self.company = make_company('q4-co')
        self.api = auth_client(make_user(self.company, 'q4user'))
        self.devis = make_devis(self.company, ref='DEV-ROOF-Q4-0001')

    def _post_image(self, api, devis, data=PNG_BYTES):
        from django.core.files.uploadedfile import SimpleUploadedFile
        up = SimpleUploadedFile('snap.png', data, content_type='image/png')
        with mock.patch(
            'apps.ventes.quote_engine.builder._ensure_pdf_bucket'
        ), mock.patch(
            'apps.ventes.utils.pdf.upload_roof_image'
        ), mock.patch(
            'apps.ventes.utils.pdf.roof_image_signed_url',
            return_value='https://minio/signed?x=1',
        ):
            return api.post(
                f'/api/django/ventes/devis/{devis.id}/roof-image/',
                {'image': up}, format='multipart')

    def test_upload_sets_key_and_returns_signed_url(self):
        resp = self._post_image(self.api, self.devis)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.roof_image,
            f'roofs/{self.company.id}/{self.devis.reference}.png')
        self.assertIn('url', resp.data)

    def test_reject_non_image(self):
        resp = self._post_image(self.api, self.devis, data=b'not an image')
        self.assertEqual(resp.status_code, 400)

    def test_cross_tenant_404(self):
        other = make_company('q4-other')
        other_api = auth_client(make_user(other, 'q4other'))
        resp = self._post_image(other_api, self.devis)
        self.assertEqual(resp.status_code, 404)

    def test_signed_url_helper_scopes_pdf_bucket(self):
        from apps.ventes.utils import pdf as pdfmod
        captured = {}

        class FakeClient:
            def generate_presigned_url(self, op, Params, ExpiresIn):
                captured.update(Params)
                return 'http://signed'
        with mock.patch.object(pdfmod, 'get_minio_client',
                               return_value=FakeClient()):
            url = pdfmod.roof_image_signed_url('roofs/1/x.png')
        self.assertEqual(url, 'http://signed')
        self.assertEqual(captured['Key'], 'roofs/1/x.png')


class TestQ5BuilderGuard(TestCase):
    """Q5 — layout figures + roof render feed the quote data only when present;
    without a layout the built data is byte-identical."""

    def setUp(self):
        self.company = make_company('q5-co')
        self.devis = make_devis(self.company, ref='DEV-Q5-0001')

    def test_no_layout_output_unchanged(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        baseline = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        # Re-build after asserting the guard added nothing.
        self.assertNotIn('roof_image_key', baseline)
        # No roof_layout/roof_image set → identical re-run.
        again = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.assertEqual(baseline, again)

    def test_layout_drives_figures(self):
        """PVUNI (fondateur 18/08/2026) — le calepinage apporte la PRODUCTION,
        jamais la PUISSANCE.

        Ce test exigeait l'inverse : ``puissance_kwc == 9.9`` (le kWc du
        calepinage) alors que les lignes du devis disent 12 × 550 W = 6,6 kWc.
        C'est exactement le défaut qui a produit l'incident DEV-202608-0007 —
        « 9 panneaux × 710 W » imprimé à côté de « 6,48 kWc » (= 9 × 720, la
        constante roofPro). Les LIGNES sont la source unique : le calepinage
        garde sa modélisation de site (production, économies), recalée sur la
        taille réellement vendue.
        """
        from apps.ventes.quote_engine.builder import build_quote_data
        before = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        self.devis.roof_layout = {
            'result': {'panels': 12, 'kwc': 9.9,
                       'annualKwh': 15000, 'savings': 12000}}
        self.devis.roof_image = 'roofs/1/DEV-Q5-0001.png'
        self.devis.save(update_fields=['roof_layout', 'roof_image'])
        after = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        # La puissance reste celle des LIGNES : 12 panneaux × 550 W = 6,6 kWc,
        # avant comme après le calepinage.
        self.assertEqual(after['puissance_kwc'], 6.6)
        self.assertEqual(after['puissance_kwc'], before['puissance_kwc'])
        self.assertEqual(
            round(after['puissance_kwc'] * 1000),
            after['nb_panneaux'] * after['watt_par_panneau'])
        # Le calepinage, lui, apporte bien quelque chose : sa production
        # annuelle, RECALÉE de 9,9 kWc à 6,6 (15 000 × 6,6 / 9,9 = 10 000).
        self.assertEqual(after['prod_kwh'], 10000)
        self.assertNotEqual(before['prod_kwh'], after['prod_kwh'])
        self.assertEqual(after['roof_image_key'], 'roofs/1/DEV-Q5-0001.png')
        # 12 panneaux au calepinage, 12 sur les lignes : rien de périmé.
        self.assertFalse(after['layout_stale'])

    def test_render_still_valid_with_layout(self):
        # The full render must still produce a real PDF when a layout exists.
        store = {}
        self.devis.roof_layout = {
            'result': {'panels': 12, 'kwc': 6.6,
                       'annualKwh': 10800, 'savings': 9200}}
        self.devis.save(update_fields=['roof_layout'])
        with mock.patch(
            'apps.ventes.quote_engine.builder._ensure_pdf_bucket'
        ), mock.patch(
            'apps.ventes.utils.pdf._upload_pdf',
            side_effect=lambda b, k: store.__setitem__(k, bytes(b))
        ):
            from apps.ventes.quote_engine import generate_premium_devis_pdf
            key = generate_premium_devis_pdf(
                self.devis.id, {'pdf_mode': 'full'}, persist=False)
        self.assertTrue(store[key].startswith(b'%PDF'))


class TestQ6ProposalData(TestCase):
    """Q6 — tokenized read-only proposal data endpoint (no login)."""

    def setUp(self):
        from apps.ventes.models import ShareLink
        self.company = make_company('q6-co')
        self.devis = make_devis(self.company, ref='DEV-Q6-0001')
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _url(self, token):
        return f'/api/django/ventes/proposal/{token}/'

    def test_valid_token_returns_payload(self):
        resp = self.api.get(self._url(self.link.token))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['reference'], 'DEV-Q6-0001')
        self.assertIn('quote', resp.data)
        self.assertIn('option_totals', resp.data)
        self.assertFalse(resp.data['accepted'])
        self.assertEqual(resp['X-Robots-Tag'].split(',')[0], 'noindex')

    def test_invalid_token_404(self):
        self.assertEqual(self.api.get(self._url('nope')).status_code, 404)

    def test_expired_token_404(self):
        from django.utils import timezone
        self.link.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.link.save(update_fields=['expires_at'])
        self.assertEqual(
            self.api.get(self._url(self.link.token)).status_code, 404)

    def test_no_cross_tenant_leak(self):
        # A second company's devis has its own token; this token never reveals it
        other = make_company('q6-other')
        other_devis = make_devis(other, ref='DEV-Q6-OTHER')
        from apps.ventes.models import ShareLink
        other_link = ShareLink.for_devis(other_devis)
        resp = self.api.get(self._url(self.link.token))
        self.assertEqual(resp.data['reference'], 'DEV-Q6-0001')
        # the other token only ever returns the other devis
        resp2 = self.api.get(self._url(other_link.token))
        self.assertEqual(resp2.data['reference'], 'DEV-Q6-OTHER')

    def test_roof_image_url_present_when_set(self):
        self.devis.roof_image = f'roofs/{self.company.id}/DEV-Q6-0001.png'
        self.devis.save(update_fields=['roof_image'])
        with mock.patch(
            'apps.ventes.utils.pdf.roof_image_signed_url',
            return_value='https://minio/signed',
        ):
            resp = self.api.get(self._url(self.link.token))
        self.assertEqual(resp.data['roof_image_url'], 'https://minio/signed')


class TestProposalPdfRoute(TestCase):
    """T3 — flux PDF CLIENT public derrière le jeton de proposition."""

    def setUp(self):
        from apps.ventes.models import ShareLink
        self.company = make_company('pdf-co')
        self.devis = make_devis(self.company, ref='DEV-PDF-0001')
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _url(self, token):
        return f'/api/django/ventes/proposal/{token}/pdf/'

    def test_valid_token_streams_pdf(self):
        with mock.patch(
            'apps.ventes.public_views.generate_premium_devis_pdf',
            return_value='devis/1/DEV-PDF-0001.pdf',
        ), mock.patch(
            'apps.ventes.public_views.download_pdf',
            return_value=b'%PDF-1.4 fake',
        ):
            resp = self.api.get(self._url(self.link.token))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('inline', resp['Content-Disposition'])
        self.assertIn('Devis_DEV-PDF-0001.pdf', resp['Content-Disposition'])
        self.assertEqual(resp['X-Robots-Tag'].split(',')[0], 'noindex')
        self.assertTrue(bytes(resp.content).startswith(b'%PDF'))

    def test_invalid_token_404(self):
        resp = self.api.get(self._url('nope'))
        self.assertEqual(resp.status_code, 404)

    def test_expired_token_404(self):
        from django.utils import timezone
        self.link.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.link.save(update_fields=['expires_at'])
        resp = self.api.get(self._url(self.link.token))
        self.assertEqual(resp.status_code, 404)

    def test_render_failure_is_friendly_404(self):
        with mock.patch(
            'apps.ventes.public_views.generate_premium_devis_pdf',
            side_effect=RuntimeError('boom'),
        ):
            resp = self.api.get(self._url(self.link.token))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp['X-Robots-Tag'].split(',')[0], 'noindex')


class TestProposalMonthlyArrays(TestCase):
    """T4 — séries mensuelles production + consommation dans proposal_data."""

    def setUp(self):
        from apps.ventes.models import ShareLink
        self.company = make_company('t4-co')
        self.devis = make_devis(self.company, ref='DEV-T4-0001')
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _data(self, token=None):
        token = token or self.link.token
        return self.api.get(f'/api/django/ventes/proposal/{token}/')

    def test_monthly_production_real_annual_distributed(self):
        resp = self._data()
        self.assertEqual(resp.status_code, 200, resp.data)
        prod = resp.data['monthly_production']
        self.assertEqual(len(prod), 12)
        annual = resp.data['quote']['prod_kwh']
        # La somme distribuée colle au total RÉEL (tolérance d'arrondi).
        self.assertAlmostEqual(sum(prod), annual, delta=12)
        # Profil saisonnier : un mois d'été > un mois d'hiver.
        self.assertGreater(prod[5], prod[11])

    def test_monthly_consumption_empty_without_bills(self):
        resp = self._data()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['monthly_consumption'], [])

    def test_monthly_consumption_empty_without_a_real_tariff(self):
        """M10 (audit adversarial du 19/08/2026) — PAS DE BARÈME RÉEL, PAS DE
        COURBE. Une facture SANS distributeur ne peut être convertie en kWh que
        par un prix plat de repli ; ``kwh_from_bill`` le signale
        (``estimation``) et ce drapeau était JETÉ : la page publiait une simple
        division par un forfait, présentée comme une mesure de consommation.
        La série part vide et la page masque le graphe — comme elle le fait
        déjà pour un devis sans facture."""
        from apps.crm.models import Lead
        lead = Lead.objects.create(
            company=self.company, nom='SansBareme', client=self.devis.client,
            facture_hiver='875', ete_differente=False)   # aucun distributeur
        self.devis.lead = lead
        self.devis.save(update_fields=['lead'])
        resp = self._data()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['monthly_consumption'], [])

    def test_monthly_consumption_winter_year_round(self):
        from apps.crm.models import Lead
        lead = Lead.objects.create(
            company=self.company, nom='Conso', client=self.devis.client,
            facture_hiver='875', ete_differente=False,
            distributeur='onee')
        self.devis.lead = lead
        self.devis.save(update_fields=['lead'])
        resp = self._data()
        conso = resp.data['monthly_consumption']
        self.assertEqual(len(conso), 12)
        # Tous les mois identiques (été non différent). M10 (audit du
        # 19/08/2026) — la conversion MAD→kWh n'est servie QUE sur un barème
        # RÉEL : le lead porte donc son distributeur, et 875 MAD se lisent au
        # barème national par tranches (539 kWh), plus par une division par un
        # forfait de 1,20 MAD/kWh présentée comme une mesure.
        self.assertTrue(all(v == 539 for v in conso))

    def test_monthly_consumption_summer_split(self):
        from apps.crm.models import Lead
        lead = Lead.objects.create(
            company=self.company, nom='Split', client=self.devis.client,
            facture_hiver='1200', facture_ete='600', ete_differente=True,
            distributeur='onee')
        self.devis.lead = lead
        self.devis.save(update_fields=['lead'])
        resp = self._data()
        conso = resp.data['monthly_consumption']
        self.assertEqual(len(conso), 12)
        # M10 — barème RÉEL exigé (le lead porte son distributeur), donc
        # conversion par tranches : 1200 MAD → 739 kWh, 600 MAD → 427 kWh.
        # Ce que ce test protège est la MÉCANIQUE de répartition, pas le
        # tarif : un mois d'été (index 5 = Juin) reste sous un mois d'hiver.
        self.assertEqual(conso[0], 739)
        self.assertEqual(conso[5], 427)
        self.assertLess(conso[5], conso[0])

    def test_consumption_resolves_via_client_when_no_direct_lead(self):
        # Devis sans lead direct mais dont le client porte un lead avec facture.
        from apps.crm.models import Lead
        Lead.objects.create(
            company=self.company, nom='ViaClient', client=self.devis.client,
            facture_hiver='1000', ete_differente=False, distributeur='onee')
        self.assertIsNone(self.devis.lead)
        resp = self._data()
        conso = resp.data['monthly_consumption']
        self.assertEqual(len(conso), 12)
        # M10 — ce que ce test protège est la RÉSOLUTION du lead via le
        # client, pas le tarif : le lead porte son distributeur, donc 1000 MAD
        # se lisent au barème national par tranches (616 kWh).
        self.assertEqual(conso[0], 616)


class _Q7ProposalAcceptBase(TestCase):
    """Q7 — shared fixture for every tokenized e-signature acceptance
    scenario.

    SHARD SPLIT (24/08/2026) — this used to be ONE class,
    ``TestQ7ProposalAccept``, measured at 254.8 s in
    ``scripts/ci_shard_class_timings.json`` (run 32711511999): the single
    slowest indivisible block of the whole suite, because ``accept_devis``
    (``apps/ventes/services.py``) calls the REAL premium quote engine
    (``generate_premium_devis_pdf`` via ``_store_signed_pdf``, rule #4) to
    persist the signed PDF on every successful acceptance — a genuine
    WeasyPrint render, not test overhead. Three of the five scenarios below
    (Success/Idempotence/Chain) reach that render; the other two
    (Validation/Token) fail before ``accept_devis`` is ever called and are
    comparatively cheap. Splitting by scenario turns one 254.8 s block into
    five, letting the LPT scheduler in ``scripts/ci_shard.py`` place each on
    whichever lane has room instead of pinning one lane to the whole cost.

    Each scenario keeps ITS OWN ``setUp`` fixture (company/client/devis/
    ShareLink) via this base class — unittest already re-runs ``setUp`` once
    per test method regardless of class grouping, so this is not new
    duplication, it is the existing per-test cost, now visible as separate
    schedulable units. That is the price of parallelization, not a
    weakening of any test."""

    def setUp(self):
        from apps.ventes.models import ShareLink
        self.company = make_company('q7-co')
        self.devis = make_devis(self.company, ref='DEV-Q7-0001')
        self.devis.statut = 'envoye'
        self.devis.save(update_fields=['statut'])
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _url(self, token):
        return f'/api/django/ventes/proposal/{token}/accept/'


class TestQ7ProposalAcceptSuccess(_Q7ProposalAcceptBase):
    """Q7 — signature réussie : bascule de statut + tampon écrit.

    Rend un PDF signé RÉEL via le moteur premium (``_store_signed_pdf``) —
    c'est la portion coûteuse historique de l'ex-``TestQ7ProposalAccept``."""

    def test_accept_flips_status_and_writes_stamp(self):
        resp = self.api.post(
            self._url(self.link.token),
            {'nom': 'Salma Bennani', 'consent_esign': True},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')
        self.assertEqual(self.devis.accepte_par_nom, 'Salma Bennani')
        self.assertIsNotNone(self.devis.date_acceptation)
        # chatter carries the acceptance + IP note
        bodies = [a.body or '' for a in self.devis.activites.all()]
        self.assertTrue(any('IP' in b for b in bodies))


class TestQ7ProposalAcceptValidation(_Q7ProposalAcceptBase):
    """Q7 — validation avant toute écriture (nom requis).

    Échoue AVANT ``accept_devis`` : pas de rendu PDF, scénario léger."""

    def test_name_required(self):
        resp = self.api.post(self._url(self.link.token), {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')


class TestQ7ProposalAcceptIdempotence(_Q7ProposalAcceptBase):
    """Q7 — double soumission idempotente.

    Le premier POST rend un PDF réel (accepte) ; le second est un no-op
    AVANT tout rendu (déjà accepté) — un seul rendu au total."""

    def test_idempotent_double_submit(self):
        first = self.api.post(
            self._url(self.link.token),
            {'nom': 'A', 'consent_esign': True}, format='json')
        self.assertEqual(first.status_code, 200)
        second = self.api.post(
            self._url(self.link.token),
            {'nom': 'B', 'consent_esign': True}, format='json')
        self.assertEqual(second.status_code, 200, second.data)
        self.devis.refresh_from_db()
        # Still the first signer; no second stamp.
        self.assertEqual(self.devis.accepte_par_nom, 'A')
        # exactly one acceptance event recorded
        self.assertEqual(self.devis.statut, 'accepte')


class TestQ7ProposalAcceptToken(_Q7ProposalAcceptBase):
    """Q7 — jeton invalide → 404 amical.

    Échoue AVANT ``accept_devis`` : pas de rendu PDF, scénario léger."""

    def test_invalid_token_404(self):
        self.assertEqual(
            self.api.post(self._url('bad'),
                          {'nom': 'X', 'consent_esign': True}, format='json')
            .status_code, 404)


class TestQ7ProposalAcceptChain(_Q7ProposalAcceptBase):
    """Q7 — la chaîne BonCommande/Facture reste préservée 1:1 après une
    acceptation tokenisée, exactement comme une acceptation in-app.

    Rend un PDF signé RÉEL via le moteur premium (même coût que Success)."""

    def test_bon_commande_chain_preserved(self):
        # After tokenized accept, the devis can be converted to a BC exactly
        # like an in-app acceptance (chain preserved 1:1).
        self.api.post(self._url(self.link.token),
                      {'nom': 'Chain', 'consent_esign': True},
                      format='json')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')
