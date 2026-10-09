"""AFAC60 (C-AFAC-054) — « Déclarer une remise » marche depuis l'écran :
``technicien`` facultatif en entrée (défaut = l'appelant), et filtre serveur
``GET paiements/?remisable=1`` tiré du MÊME prédicat que la déclaration
(``paiements_remisables``).

Rejoue les sondes FUI-3b / L2-C-AFAC-054 (corps de l'écran ⇒ 400
« technicien obligatoire » ; `/paiements/` sert le paiement remis et le
rejeté). APIClient, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_remise_encaissement_ecran"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()
REMISES = '/api/django/ventes/remises-encaissement/'
PAIEMENTS = '/api/django/ventes/paiements/'


class RemiseCorpsEcranTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture, Paiement
        from authentication.models import Company
        self.company = Company.objects.create(nom='AFAC60', slug='afac60-co')
        self.resp = User.objects.create_user(
            username='afac60_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.resp)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='AFAC60',
            email='afac60@example.invalid')
        facture = Facture.objects.create(
            company=self.company, reference='FAC-AFAC60-0001', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
            montant_ttc=Decimal('12000'))

        def _p(mode, statut=Paiement.Statut.ENCAISSE):
            return Paiement.objects.create(
                company=self.company, facture=facture, montant=Decimal('100'),
                date_paiement=date(2026, 10, 1), mode=mode, statut=statut,
                created_by=self.resp)
        self.p1 = _p(Paiement.Mode.ESPECES)
        self.p2 = _p(Paiement.Mode.CHEQUE, Paiement.Statut.REJETE)
        self.p3 = _p(Paiement.Mode.ESPECES)
        self.p4 = _p(Paiement.Mode.VIREMENT)
        r = self.api.post(REMISES, {
            'date_collecte': '2026-10-01', 'montant_declare': '100',
            'note': '', 'technicien': self.resp.id,
            'lignes': [{'paiement': self.p3.id}]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def _remisables(self):
        r = self.api.get(PAIEMENTS, {'remisable': '1'})
        self.assertEqual(r.status_code, 200, r.data)
        corps = r.data
        rows = corps.get('results', corps) if isinstance(corps, dict) else corps
        return {row['id'] for row in rows}

    def _corps_ecran(self):
        return {'date_collecte': '2026-10-02', 'montant_declare': '100',
                'note': '', 'lignes': [{'paiement': self.p1.id}]}

    def test_corps_ecran_sans_technicien_cree_la_remise(self):
        from apps.ventes.models import RemiseEncaissement
        r = self.api.post(REMISES, self._corps_ecran(), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['technicien'], self.resp.id)
        self.assertTrue(r.data['reference'].startswith('REM'))
        # CLAUSE PERSISTANCE : rejouer sur P1 ⇒ 400, aucune remise vide.
        nb = RemiseEncaissement.objects.filter(company=self.company).count()
        r2 = self.api.post(REMISES, self._corps_ecran(), format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn('déjà déclaré dans la remise', str(r2.data['lignes']))
        self.assertEqual(
            RemiseEncaissement.objects.filter(company=self.company).count(),
            nb)

    def test_filtre_remisable_exclut_rejete_remis_et_virement(self):
        self.assertEqual(self._remisables(), {self.p1.id})
        self.api.post(REMISES, self._corps_ecran(), format='json')
        self.assertEqual(self._remisables(), set())
        # Sans `remisable`, la liste est inchangée (les quatre paiements).
        r = self.api.get(PAIEMENTS)
        corps = r.data
        rows = corps.get('results', corps) if isinstance(corps, dict) else corps
        self.assertTrue({self.p1.id, self.p2.id, self.p3.id, self.p4.id}
                        <= {row['id'] for row in rows})

    def test_technicien_etranger_refuse(self):
        from authentication.models import Company
        autre = Company.objects.create(nom='AFAC60 B', slug='afac60-b')
        etranger = User.objects.create_user(
            username='afac60_etranger', password='x',
            role_legacy='responsable', company=autre)
        corps = self._corps_ecran()
        corps['technicien'] = etranger.id
        r = self.api.post(REMISES, corps, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('technicien', r.data)
