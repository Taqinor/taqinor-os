"""
Tests for lead-primary quote creation: a quote started from a lead carries
BOTH the lead and its resolved client, with no duplicate client records.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_lead_quotes -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug='lead-devis-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Lead Devis Co'},
    )
    return company


class TestLeadQuoteCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='lead_devis_user', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _create_from_lead(self, lead, extra=None):
        payload = {
            'lead': lead.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }
        payload.update(extra or {})
        return self.api.post('/api/django/ventes/devis/', payload, format='json')

    def test_quote_from_lead_attaches_lead_and_resolved_client(self):
        lead = Lead.objects.create(
            company=self.company, nom='Tahiri', prenom='Yasmine',
            telephone='+212600000005', ville='Casablanca',
            facture_hiver=700, ete_differente=False,
        )
        resp = self._create_from_lead(lead)
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.lead_id, lead.id)
        self.assertIsNotNone(devis.client_id)
        lead.refresh_from_db()
        self.assertEqual(devis.client_id, lead.client_id)
        self.assertEqual(devis.client.nom, 'Tahiri')

    def test_second_quote_same_lead_reuses_client(self):
        lead = Lead.objects.create(
            company=self.company, nom='Mansouri', email='m@example.com')
        first = self._create_from_lead(lead)
        second = self._create_from_lead(lead)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        d1 = Devis.objects.get(pk=first.data['id'])
        d2 = Devis.objects.get(pk=second.data['id'])
        self.assertEqual(d1.client_id, d2.client_id)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)

    def test_quote_from_lead_with_discount_kept_exactly(self):
        lead = Lead.objects.create(company=self.company, nom='Remise')
        resp = self._create_from_lead(lead, {'remise_globale': '7.5'})
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(str(devis.remise_globale), '7.50')

    def test_quote_without_lead_or_client_rejected(self):
        resp = self.api.post('/api/django/ventes/devis/', {
            'statut': 'brouillon', 'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_foreign_lead_rejected(self):
        other = make_company(slug='lead-devis-other')
        foreign = Lead.objects.create(company=other, nom='Foreign')
        resp = self._create_from_lead(foreign)
        self.assertEqual(resp.status_code, 400)

    def test_client_only_path_still_works(self):
        client = Client.objects.create(
            company=self.company, nom='Direct', email='direct@example.com')
        resp = self.api.post('/api/django/ventes/devis/', {
            'client': client.id, 'statut': 'brouillon',
            'taux_tva': '20.00', 'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis = Devis.objects.get(pk=resp.data['id'])
        self.assertEqual(devis.client_id, client.id)
        self.assertIsNone(devis.lead_id)

    def test_lead_retrieve_lists_new_devis(self):
        # BUG 2 : un devis créé depuis le lead doit apparaître dans le lead
        # rechargé (source de rafraîchissement de la liste côté fiche).
        lead = Lead.objects.create(
            company=self.company, nom='Listé', facture_hiver=700)
        resp = self._create_from_lead(lead)
        self.assertEqual(resp.status_code, 201, resp.data)
        devis_id = resp.data['id']
        retr = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(retr.status_code, 200)
        ids = [d['id'] for d in retr.data.get('devis', [])]
        self.assertIn(devis_id, ids)

    def test_proposal_serves_inline_pdf(self):
        # BUG 1 : l'endpoint /proposal sert un PDF inline chargeable par le
        # navigateur (type application/pdf, pas du JSON ni une URL MinIO).
        from unittest import mock
        lead = Lead.objects.create(
            company=self.company, nom='Pdf', facture_hiver=700)
        devis_id = self._create_from_lead(lead).data['id']
        with mock.patch(
            'apps.ventes.quote_engine.generate_premium_devis_pdf',
            return_value='devis/fake.pdf',
        ), mock.patch(
            'apps.ventes.utils.pdf.download_pdf',
            return_value=b'%PDF-1.4 fake pdf bytes',
        ):
            resp = self.api.get(
                f'/api/django/ventes/devis/{devis_id}/proposal/?pdf_mode=onepage')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('inline', resp['Content-Disposition'])
        self.assertTrue(resp.content.startswith(b'%PDF'))


class TestProposalRealRender(TestCase):
    """RÉGRESSION (aperçu devis cassé) : on rend RÉELLEMENT le PDF via le moteur
    vendu — moteur NON mocké — pour les trois formats de l'aperçu du panneau
    lead (Premium, 1 page, Inclure l'étude). L'ancien test mockait le moteur et
    ne pouvait donc PAS détecter un échec de rendu : il vérifiait juste qu'un
    endpoint répond 200. Ici on prouve que les octets servis sont un vrai PDF
    chargeable (signature %PDF, taille réaliste), ce que l'iframe blob affiche.
    Seul l'aller-retour MinIO est simulé : les octets traversent intacts."""

    def setUp(self):
        from decimal import Decimal
        from apps.stock.models import Produit
        from apps.ventes.models import LigneDevis
        self.company = make_company(slug='proposal-render-co')
        self.user = User.objects.create_user(
            username='proposal_render_user', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Salma',
            email='s@example.com', telephone='+212600000009',
            adresse='Anfa, Casablanca',
        )
        # Devis réaliste avec lignes (mêmes ingrédients que les tests moteur) :
        # panneaux + onduleur + structure -> rendu premium complet.
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-RENDER-0001', client=client,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
        )
        for desig, qty, pu in [
            ('Panneau mono 550W', '12', '1100'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Structures acier', '12', '375'),
            ('Installation', '1', '4000'),
        ]:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'RND-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100,
            )
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'),
            )

    def _get_proposal(self, query=''):
        """Rend réellement le PDF : moteur réel, seul MinIO (upload/download)
        est simulé via un magasin en mémoire pour faire transiter les octets."""
        from unittest import mock
        store = {}

        def fake_upload(pdf_bytes, key):
            store[key] = bytes(pdf_bytes)

        def fake_download(key):
            return store[key]

        with mock.patch(
            'apps.ventes.quote_engine.builder._ensure_pdf_bucket'
        ), mock.patch(
            'apps.ventes.utils.pdf._upload_pdf', side_effect=fake_upload
        ), mock.patch(
            'apps.ventes.utils.pdf.download_pdf', side_effect=fake_download
        ):
            return self.api.get(
                f'/api/django/ventes/devis/{self.devis.id}/proposal/{query}')

    def _assert_valid_pdf(self, resp):
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('inline', resp['Content-Disposition'])
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'%PDF'),
                        'le corps servi doit être un vrai PDF (%PDF)')
        # Un vrai rendu fait des dizaines de Ko ; un PDF quasi vide trahit un
        # échec silencieux. On exige une taille plancher réaliste.
        self.assertGreater(len(body), 10000, 'PDF trop petit -> rendu raté')

    def test_premium_full_renders_valid_pdf(self):
        self._assert_valid_pdf(self._get_proposal('?pdf_mode=full'))

    def test_onepage_renders_valid_pdf(self):
        self._assert_valid_pdf(self._get_proposal('?pdf_mode=onepage'))

    def test_premium_with_etude_renders_valid_pdf(self):
        self._assert_valid_pdf(
            self._get_proposal('?pdf_mode=full&include_etude=1'))
