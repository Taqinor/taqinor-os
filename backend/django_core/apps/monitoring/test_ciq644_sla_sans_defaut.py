"""CIQ644 — SLA de disponibilité SANS 98 % pré-rempli ; l'indicateur
s'appelle « indice de suivi » ; aucune pénalité tant que l'engagement de
production n'est pas validé (``garantie_production_autorisee``, CIQ622).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.monitoring.test_ciq644_sla_sans_defaut"
"""
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

from django.core.exceptions import ValidationError
from django.db import migrations
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading, SlaDisponibilite
from apps.monitoring.selectors import disponibilite_vs_garantie
from apps.parametres.models import CompanyProfile


def _inst(company, ref):
    client = Client.objects.create(
        company=company, nom='Cli', prenom=ref,
        email=f'{ref.lower()}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        puissance_installee_kwc=Decimal('10'))


class SlaSansDefautTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq644-co', defaults={'nom': 'CIQ644 Co'})
        self.today = date(2026, 6, 30)

    def test_aucun_taux_par_defaut(self):
        champ = SlaDisponibilite._meta.get_field('disponibilite_garantie_pct')
        self.assertFalse(champ.has_default())

    def test_full_clean_sans_taux_refuse_en_francais(self):
        sla = SlaDisponibilite(company=self.company,
                               installation=_inst(self.company, 'CIQ644-1'))
        with self.assertRaises(ValidationError) as ctx:
            sla.full_clean()
        self.assertIn('Saisir le taux garanti',
                      str(ctx.exception.message_dict[
                          'disponibilite_garantie_pct']))

    def test_full_clean_avec_97_valide(self):
        sla = SlaDisponibilite(company=self.company,
                               installation=_inst(self.company, 'CIQ644-2'),
                               disponibilite_garantie_pct=Decimal('97'))
        sla.full_clean()

    def _sous_garantie(self, ref):
        inst = _inst(self.company, ref)
        SlaDisponibilite.objects.create(
            company=self.company, installation=inst,
            disponibilite_garantie_pct=Decimal('98'),
            compensation_mad_par_jour_indispo=Decimal('500'))
        for i in range(8):
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=self.today - timedelta(days=i), energy_kwh=Decimal('10'))
        return disponibilite_vs_garantie(inst, window_days=10,
                                         today=self.today)

    def test_libelle_indice_de_suivi(self):
        res = self._sous_garantie('CIQ644-3')
        self.assertEqual(res['libelle_indicateur'],
                         'indice de suivi (jours avec relevé)')
        self.assertNotIn('contractuelle', res['libelle_indicateur'])

    def test_reglage_faux_penalite_null_ecart_garde(self):
        res = self._sous_garantie('CIQ644-4')
        self.assertIsNone(res['penalite_mad'])
        self.assertEqual(res['ecart_pct'], Decimal('18.00'))

    def test_reglage_vrai_penalite_actuelle(self):
        profil = CompanyProfile.get(company=self.company)
        profil.garantie_production_autorisee = True
        profil.garantie_production_validation = 'Assureur X, 02/10/2026'
        profil.save()
        res = self._sous_garantie('CIQ644-5')
        self.assertEqual(res['penalite_mad'], Decimal('900.00'))

    def test_ligne_sans_taux_ni_ecart_ni_penalite(self):
        inst = _inst(self.company, 'CIQ644-6')
        SlaDisponibilite.objects.create(company=self.company,
                                        installation=inst)
        res = disponibilite_vs_garantie(inst, window_days=10,
                                        today=self.today)
        self.assertTrue(res['has_sla'])
        self.assertIsNone(res['disponibilite_garantie_pct'])
        self.assertIsNone(res['ecart_pct'])
        self.assertIsNone(res['penalite_mad'])

    def test_migration_alterfield_reversible(self):
        module = import_module(
            'apps.monitoring.migrations.0008_ciq644_sla_sans_defaut')
        self.assertEqual(len(module.Migration.operations), 1)
        op = module.Migration.operations[0]
        self.assertIsInstance(op, migrations.AlterField)
        self.assertTrue(op.reversible)
