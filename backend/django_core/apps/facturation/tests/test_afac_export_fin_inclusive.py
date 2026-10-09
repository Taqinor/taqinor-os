"""AFAC51 (C-AFAC-044) — la « Date de fin » saisie est INCLUSIVE pour tout
export comptable / journal / analyse par ``?start=&end=`` (et
``?debut=&fin=``) : ``period_bounds`` renvoie ``[start, end + 1 jour[`` ;
``?month=`` donne exactement les mêmes lignes que la plage du mois.

Rejoue la sonde FDOC-5 (`end=2026-09-30` : facture du 30/09 absente).
APIClient, exports réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_export_fin_inclusive"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class ExportFinInclusiveTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from authentication.models import Company
        self.company = Company.objects.create(nom='AFAC51', slug='afac51-co')
        self.user = User.objects.create_user(
            username='afac51_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='AFAC51',
            email='afac51@example.invalid', ice='001122334455667')
        self.f30 = Facture.objects.create(
            company=self.company, reference='FAC-AFAC51-0930', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        Facture.objects.filter(pk=self.f30.pk).update(
            date_emission=date(2026, 9, 30))
        self.f01 = Facture.objects.create(
            company=self.company, reference='FAC-AFAC51-0901', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            montant_ht=Decimal('500'), montant_tva=Decimal('100'),
            montant_ttc=Decimal('600'))
        Facture.objects.filter(pk=self.f01.pk).update(
            date_emission=date(2026, 9, 1))

    def _export(self, query):
        r = self.api.get(f'/api/django/ventes/export-comptable/?{query}'
                         '&fmt=csv')
        self.assertEqual(r.status_code, 200)
        body = (b''.join(r.streaming_content) if r.streaming else r.content)
        return body.decode('utf-8-sig', errors='replace')

    def test_export_comptable_fin_incluse(self):
        texte = self._export('start=2026-09-01&end=2026-09-30')
        self.assertIn('FAC-AFAC51-0930', texte)
        self.assertIn('FAC-AFAC51-0901', texte)

    def test_period_bounds_fin_incluse(self):
        from apps.ventes.exports import period_bounds
        self.assertEqual(
            period_bounds({'start': '2026-09-01', 'end': '2026-09-30'}),
            (date(2026, 9, 1), date(2026, 10, 1)))

    def test_analyse_facturation_fin_incluse(self):
        r = self.api.get('/api/django/ventes/etats/analyse-facturation/'
                         '?debut=2026-09-01&fin=2026-09-30')
        self.assertEqual(r.status_code, 200, r.data)
        corps = r.data
        rows = corps.get('rows', corps) if isinstance(corps, dict) else corps
        nb = sum(int(row.get('nb_factures', 0)) for row in rows)
        self.assertEqual(nb, 2)
        total = sum(Decimal(row['total_ttc']) for row in rows)
        self.assertEqual(total, Decimal('1800.00'))

    def test_mois_egal_plage_inclusive(self):
        par_mois = self._export('month=2026-09')
        par_plage = self._export('start=2026-09-01&end=2026-09-30')
        self.assertEqual(par_mois, par_plage)
