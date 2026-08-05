"""N100(e) — registre de facturation de LICENCE (console fondateur).

Surface strictement éditeur : aucun tenant ne doit pouvoir la lire ni l'écrire.
"""
from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

from ..models import FactureLicence


class FacturationLicenceTests(TestCase):
    def setUp(self):
        self.tenant = Company.objects.create(
            nom='Licence Alpha', slug='licence-alpha')
        self.autre = Company.objects.create(
            nom='Licence Beta', slug='licence-beta')
        self.fondateur = CustomUser.objects.create_superuser(
            username='fondateur_licence', password='pw62130',
            email='fondateur.licence@exemple.ma')
        self.admin_tenant = CustomUser.objects.create_user(
            username='admin_licence_alpha', password='pw62130',
            company=self.tenant, role_legacy='admin')

    def _api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    # ── Garde d'accès ───────────────────────────────────────────────────────
    def test_admin_tenant_ne_voit_pas_le_registre(self):
        resp = self._api(self.admin_tenant).get(
            '/api/django/adminops/facturation-licences/')
        self.assertIn(resp.status_code, (401, 403))

    def test_admin_tenant_ne_peut_pas_creer(self):
        resp = self._api(self.admin_tenant).post(
            '/api/django/adminops/facturation-licences/',
            {'company': self.tenant.pk, 'periode': '2026-08'}, format='json')
        self.assertIn(resp.status_code, (401, 403))
        self.assertEqual(FactureLicence.objects.count(), 0)

    def test_anonyme_refuse(self):
        resp = APIClient().get('/api/django/adminops/facturation-licences/')
        self.assertIn(resp.status_code, (401, 403))

    # ── Cycle de vie ────────────────────────────────────────────────────────
    def test_creation_brouillon_sans_reference(self):
        resp = self._api(self.fondateur).post(
            '/api/django/adminops/facturation-licences/',
            {'company': self.tenant.pk, 'periode': '2026-08',
             'montant_ht': '1000.00', 'tva': '200.00',
             'montant_ttc': '1200.00'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['statut'], 'brouillon')
        # Un brouillon ne consomme pas de numéro.
        self.assertEqual(resp.data['reference'], '')
        self.assertEqual(resp.data['periode'], '2026-08-01')

    def test_emission_attribue_une_reference_via_le_socle(self):
        resp = self._api(self.fondateur).post(
            '/api/django/adminops/facturation-licences/',
            {'company': self.tenant.pk, 'periode': '2026-08',
             'statut': 'emise', 'montant_ttc': '1200.00'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['reference'].startswith('LIC-'))
        self.assertIsNotNone(resp.data['date_emission'])

    def test_references_successives_ne_collisionnent_pas(self):
        refs = set()
        for _ in range(3):
            resp = self._api(self.fondateur).post(
                '/api/django/adminops/facturation-licences/',
                {'company': self.tenant.pk, 'periode': '2026-08',
                 'statut': 'emise'}, format='json')
            refs.add(resp.data['reference'])
        self.assertEqual(len(refs), 3)

    def test_periode_invalide_refusee(self):
        resp = self._api(self.fondateur).post(
            '/api/django/adminops/facturation-licences/',
            {'company': self.tenant.pk, 'periode': 'pas-une-date'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_societe_inconnue_404(self):
        resp = self._api(self.fondateur).post(
            '/api/django/adminops/facturation-licences/',
            {'company': 999999, 'periode': '2026-08'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_marquer_payee_est_idempotent(self):
        facture = FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 8, 1),
            montant_ttc=1200, statut=FactureLicence.Statut.EMISE,
            reference='LIC-202608-0001')
        api = self._api(self.fondateur)
        premier = api.post(
            f'/api/django/adminops/facturation-licences/{facture.pk}/marquer-payee/')
        self.assertEqual(premier.status_code, 200)
        self.assertEqual(premier.data['statut'], 'payee')
        date_paiement = premier.data['date_paiement']

        second = api.post(
            f'/api/django/adminops/facturation-licences/{facture.pk}/marquer-payee/')
        self.assertEqual(second.status_code, 200)
        # Le second pointage ne réécrit pas la date d'encaissement.
        self.assertEqual(second.data['date_paiement'], date_paiement)

    def test_date_paiement_conserve_le_jour(self):
        """Une date d'encaissement est une VRAIE date : le jour ne doit pas
        être écrasé par la normalisation « 1er du mois » des périodes."""
        facture = FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 8, 1),
            statut=FactureLicence.Statut.EMISE, reference='LIC-202608-0009')
        resp = self._api(self.fondateur).post(
            f'/api/django/adminops/facturation-licences/{facture.pk}/marquer-payee/',
            {'date_paiement': '2026-08-17'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['date_paiement'], '2026-08-17')
        # La période, elle, reste bien normalisée au 1er du mois.
        self.assertEqual(resp.data['periode'], '2026-08-01')

    def test_total_du_exclut_les_factures_payees(self):
        FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 7, 1),
            montant_ttc=1000, statut=FactureLicence.Statut.EMISE)
        FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 6, 1),
            montant_ttc=5000, statut=FactureLicence.Statut.PAYEE)
        resp = self._api(self.fondateur).get(
            '/api/django/adminops/facturation-licences/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.data['total_du_ttc']), 1000.0)

    def test_filtre_par_tenant(self):
        FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 8, 1))
        FactureLicence.objects.create(
            company=self.autre, periode=date(2026, 8, 1))
        resp = self._api(self.fondateur).get(
            f'/api/django/adminops/facturation-licences/?company={self.tenant.pk}')
        self.assertEqual(len(resp.data['results']), 1)

    def test_export_csv(self):
        FactureLicence.objects.create(
            company=self.tenant, periode=date(2026, 8, 1),
            reference='LIC-202608-0001', montant_ttc=1200,
            statut=FactureLicence.Statut.EMISE)
        resp = self._api(self.fondateur).get(
            '/api/django/adminops/facturation-licences/export-csv/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        contenu = resp.content.decode('utf-8')
        self.assertIn('LIC-202608-0001', contenu)
        self.assertIn('Licence Alpha', contenu)

    def test_export_csv_refuse_au_tenant(self):
        resp = self._api(self.admin_tenant).get(
            '/api/django/adminops/facturation-licences/export-csv/')
        self.assertIn(resp.status_code, (401, 403))
