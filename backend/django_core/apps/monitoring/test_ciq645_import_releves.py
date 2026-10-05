"""CIQ645 — suivi de production des sites pros, phase 1 : import CSV des
relevés (source « import »), idempotent par (chantier, date, période), lignes
invalides rapportées avec leur numéro, ``company`` posée côté serveur.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.monitoring.test_ciq645_import_releves"
"""
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import migrations
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import MonitoringConfig, ProductionReading

User = get_user_model()


def _config(company, ref):
    client = Client.objects.create(
        company=company, nom='Cli', prenom=ref,
        email=f'{ref.lower()}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=ref, client=client,
        puissance_installee_kwc=Decimal('100'))
    return MonitoringConfig.objects.create(company=company, installation=inst)


def _csv(n, debut=date(2026, 9, 1), sep=';'):
    lignes = [sep.join(('date', 'periode_jours', 'energie_kwh',
                        'index_compteur'))]
    for i in range(n):
        lignes.append(sep.join(((debut + timedelta(days=i)).isoformat(), '1',
                                f'{400 + i}.5', str(10000 + i))))
    return '\n'.join(lignes) + '\n'


class ImportRelevesTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq645-co', defaults={'nom': 'CIQ645 Co'})
        self.user = User.objects.create_user(
            username='ciq645_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.config = _config(self.company, 'CIQ645-1')
        self.url = (f'/api/django/monitoring/configs/{self.config.pk}/'
                    'import-releves/')

    def _releves(self):
        return ProductionReading.objects.filter(
            installation=self.config.installation)

    def test_30_lignes_30_releves_import(self):
        fichier = SimpleUploadedFile('releves.csv', _csv(30).encode('utf-8'),
                                     content_type='text/csv')
        resp = self.api.post(self.url, {'fichier': fichier},
                             format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['crees'], 30)
        self.assertEqual(resp.data['erreurs'], [])
        self.assertEqual(self._releves().count(), 30)
        self.assertEqual(self._releves().filter(source='import').count(), 30)
        self.assertEqual(
            set(self._releves().values_list('company_id', flat=True)),
            {self.company.pk})
        premier = self._releves().get(date=date(2026, 9, 1))
        self.assertEqual(premier.energy_kwh, Decimal('400.50'))
        self.assertIn('10000', premier.note)

    def test_reimport_zero_doublon(self):
        self.api.post(self.url, {'csv': _csv(30)}, format='json')
        resp = self.api.post(self.url, {'csv': _csv(30, sep=',')},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['crees'], 0)
        self.assertEqual(resp.data['doublons'], 30)
        self.assertEqual(self._releves().count(), 30)

    def test_energie_negative_rapportee_non_creee(self):
        texte = ('date;periode_jours;energie_kwh\n'
                 '2026-09-01;1;420\n'
                 '02/09/2026;1;-5\n'
                 'pas-une-date;1;300\n')
        resp = self.api.post(self.url, {'csv': texte}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['crees'], 1)
        lignes = {e['ligne']: e['motif'] for e in resp.data['erreurs']}
        self.assertIn('négative', lignes[3])
        self.assertIn('Date illisible', lignes[4])
        self.assertEqual(self._releves().count(), 1)

    def test_chantier_d_une_autre_societe_404(self):
        autre, _ = Company.objects.get_or_create(
            slug='ciq645-autre', defaults={'nom': 'CIQ645 Autre'})
        config_autre = _config(autre, 'CIQ645-2')
        resp = self.api.post(
            f'/api/django/monitoring/configs/{config_autre.pk}/import-releves/',
            {'csv': _csv(2)}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(ProductionReading.objects.filter(
            installation=config_autre.installation).exists())

    def test_migration_de_choix(self):
        module = import_module(
            'apps.monitoring.migrations.0009_ciq645_source_import')
        op = module.Migration.operations[0]
        self.assertIsInstance(op, migrations.AlterField)
        self.assertIn(('import', 'Import CSV'), op.field.choices)
