"""Tests N25 — acceptation explicite d'un devis (date + nom) + chatter."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='acc-co', nom='Acc Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisAcceptation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='acc_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Acc',
            email='acc@example.com', telephone='+212600000001')

    def _devis(self, num=1, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def _devis_deux_options(self, num=20):
        """Devis à deux options (réseau + hybride/batterie) → nb_options == 2."""
        devis = self._devis(num=num)
        lignes = [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ]
        for desig, qty, pu in lignes:
            sku = f'{num}-{desig[:12]}'
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=sku,
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def test_accepter_sets_metadata_and_chatter(self):
        devis = self._devis()
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Bennani', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertEqual(str(devis.date_acceptation), '2026-06-10')
        self.assertEqual(devis.accepte_par_nom, 'M. Bennani')
        acts = DevisActivity.objects.filter(devis=devis)
        self.assertEqual(acts.count(), 1)
        self.assertIn('Bennani', acts.first().body)

    def test_accepter_defaults_date_to_today(self):
        devis = self._devis(num=2)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.date_acceptation, timezone.now().date())

    def test_invalid_date_rejected(self):
        devis = self._devis(num=3)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'date': 'pas-une-date'}, format='json')
        self.assertEqual(r.status_code, 400)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')

    def test_historique_and_noter(self):
        devis = self._devis(num=4)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/noter/',
            {'body': 'Relancé le client par téléphone.'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        h = self.api.get(f'/api/django/ventes/devis/{devis.id}/historique/')
        self.assertEqual(h.status_code, 200)
        bodies = [a['body'] for a in h.data]
        self.assertTrue(any('Relancé' in (b or '') for b in bodies))

    def test_empty_note_rejected(self):
        devis = self._devis(num=5)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/noter/',
            {'body': '   '}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_acceptation_enables_chantier_creation(self):
        """L'acceptation est le déclencheur : creer-depuis-devis exige accepté."""
        devis = self._devis(num=6)
        # Avant acceptation : refusé.
        r0 = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r0.status_code, 400)
        # Après acceptation : autorisé.
        self.api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                      {'nom': 'Client', 'date': '2026-06-05'}, format='json')
        r1 = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        # La date de signature du chantier reprend la date d'acceptation.
        self.assertEqual(r1.data.get('date_signature'), '2026-06-05')

    # ── A1 — option retenue (Sans batterie / Avec batterie) ──────────────

    def test_single_option_devis_infers_option(self):
        """Devis à option unique (ici vide) : l'option est déduite, pas exigée,
        et le comportement N25 (date + nom) reste intact."""
        devis = self._devis(num=10)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Bennani', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertEqual(devis.option_acceptee, 'sans_batterie')

    def test_two_option_devis_requires_explicit_option(self):
        """Devis à deux options accepté SANS option → refusé (400)."""
        devis = self._devis_deux_options(num=21)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')
        self.assertEqual(devis.option_acceptee, '')

    def test_two_option_devis_records_chosen_option(self):
        """Devis à deux options accepté AVEC option → stockée + consignée."""
        devis = self._devis_deux_options(num=22)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10',
             'option': 'avec_batterie'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertEqual(devis.option_acceptee, 'avec_batterie')
        act = DevisActivity.objects.filter(devis=devis).first()
        self.assertIn('Avec batterie', act.body)

    def test_invalid_option_rejected(self):
        """Une option inconnue est refusée (400) avant tout changement."""
        devis = self._devis_deux_options(num=23)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10',
             'option': 'banane'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')
