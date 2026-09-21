"""NTGRC33 — cadres de conformité multi-référentiels.

Garanties : le taux de couverture d'un cadre = exigences COUVERTES / total ;
le seed installe au moins la loi 09-08, est idempotent et n'écrase jamais le
mapping déjà fait ; tout reste scopé société.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.grc.models import CadreConformite, ControleInterne, ExigenceCadre
from apps.grc.selectors import taux_couverture
from authentication.models import Company
from testkit.base import TenantAPITestCase


def _cadre(company, code=CadreConformite.CODE_LOI_09_08):
    return CadreConformite.objects.create(
        company=company, code=code, intitule='Cadre de test')


def _exigence(company, cadre, code, statut, controle_ref=''):
    return ExigenceCadre.objects.create(
        company=company, cadre=cadre, code_exigence=code,
        intitule=f'Exigence {code}', statut_couverture=statut,
        controle_ref=controle_ref)


class TauxCouvertureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC33 SA', slug='ntgrc33')

    def test_le_taux_est_couvertes_sur_total(self):
        cadre = _cadre(self.company)
        _exigence(self.company, cadre, 'A1', ExigenceCadre.COUVERTURE_COUVERT)
        _exigence(self.company, cadre, 'A2', ExigenceCadre.COUVERTURE_COUVERT)
        _exigence(self.company, cadre, 'A3', ExigenceCadre.COUVERTURE_NON)
        _exigence(self.company, cadre, 'A4', ExigenceCadre.COUVERTURE_NON)
        couverture = taux_couverture(self.company, cadre)
        self.assertEqual(couverture['total'], 4)
        self.assertEqual(couverture['couvert'], 2)
        self.assertEqual(couverture['taux_pct'], 50.0)

    def test_le_partiel_ne_compte_pas_comme_couvert(self):
        cadre = _cadre(self.company)
        _exigence(self.company, cadre, 'A1', ExigenceCadre.COUVERTURE_COUVERT)
        _exigence(self.company, cadre, 'A2', ExigenceCadre.COUVERTURE_PARTIEL)
        couverture = taux_couverture(self.company, cadre)
        self.assertEqual(couverture['taux_pct'], 50.0)
        self.assertEqual(couverture['partiel'], 1)
        # L'avancement interne, lui, crédite le partiel d'une demi-exigence.
        self.assertEqual(couverture['taux_avec_partiel_pct'], 75.0)

    def test_un_cadre_sans_exigence_vaut_zero(self):
        cadre = _cadre(self.company)
        couverture = taux_couverture(self.company, cadre)
        self.assertEqual(couverture['total'], 0)
        self.assertEqual(couverture['taux_pct'], 0.0)

    def test_le_taux_ne_compte_pas_les_exigences_d_un_autre_cadre(self):
        cadre = _cadre(self.company)
        autre = _cadre(self.company, code=CadreConformite.CODE_ISO27001)
        _exigence(self.company, cadre, 'A1', ExigenceCadre.COUVERTURE_COUVERT)
        _exigence(self.company, autre, 'B1', ExigenceCadre.COUVERTURE_NON)
        self.assertEqual(taux_couverture(self.company, cadre)['taux_pct'],
                         100.0)


class SeedCadresTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC33 S', slug='ntgrc33-s')

    def test_le_seed_installe_au_moins_la_loi_09_08(self):
        call_command('seed_cadres_conformite',
                     '--company', str(self.company.pk), stdout=StringIO())
        cadre = CadreConformite.objects.get(
            company=self.company, code=CadreConformite.CODE_LOI_09_08)
        self.assertGreaterEqual(cadre.exigences.count(), 5)
        self.assertEqual(
            CadreConformite.objects.filter(company=self.company).count(), 2)

    def test_le_seed_est_idempotent(self):
        for _ in range(3):
            call_command('seed_cadres_conformite',
                         '--company', str(self.company.pk), stdout=StringIO())
        self.assertEqual(
            CadreConformite.objects.filter(company=self.company).count(), 2)
        self.assertEqual(
            ExigenceCadre.objects.filter(company=self.company).count(), 16)

    def test_le_seed_n_ecrase_pas_le_mapping_deja_fait(self):
        call_command('seed_cadres_conformite',
                     '--company', str(self.company.pk), stdout=StringIO())
        exigence = ExigenceCadre.objects.filter(
            company=self.company, code_exigence='09-08-A5').first()
        exigence.controle_ref = '99'
        exigence.statut_couverture = ExigenceCadre.COUVERTURE_COUVERT
        exigence.save()
        call_command('seed_cadres_conformite',
                     '--company', str(self.company.pk), stdout=StringIO())
        exigence.refresh_from_db()
        self.assertEqual(exigence.controle_ref, '99')
        self.assertEqual(exigence.statut_couverture,
                         ExigenceCadre.COUVERTURE_COUVERT)

    def test_le_seed_ne_rallume_pas_un_cadre_desactive(self):
        call_command('seed_cadres_conformite',
                     '--company', str(self.company.pk), stdout=StringIO())
        cadre = CadreConformite.objects.get(
            company=self.company, code=CadreConformite.CODE_ISO27001)
        cadre.actif = False
        cadre.save()
        call_command('seed_cadres_conformite',
                     '--company', str(self.company.pk), stdout=StringIO())
        cadre.refresh_from_db()
        self.assertFalse(cadre.actif)


class EndpointCadresTests(TenantAPITestCase):
    BASE = '/api/django/grc/cadres-conformite/'
    EXIGENCES = '/api/django/grc/exigences-cadre/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe(self):
        r = self._admin().post(
            self.BASE, {'code': 'RGPD', 'intitule': 'RGPD'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        cadre = CadreConformite.objects.get(pk=r.data['id'])
        self.assertEqual(cadre.company, self.company)
        self.assertEqual(r.data['couverture']['total'], 0)

    def test_une_exigence_couverte_doit_nommer_son_controle(self):
        cadre = _cadre(self.company)
        r = self._admin().post(
            self.EXIGENCES,
            {'cadre': cadre.pk, 'code_exigence': 'A1', 'intitule': 'X',
             'statut_couverture': 'couvert'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('controle_ref', r.data)

    def test_un_controle_d_une_autre_societe_est_refuse(self):
        cadre = _cadre(self.company)
        etranger = ControleInterne.objects.create(
            company=self.other_company, code='ACC-01', intitule='Revue')
        r = self._admin().post(
            self.EXIGENCES,
            {'cadre': cadre.pk, 'code_exigence': 'A1', 'intitule': 'X',
             'statut_couverture': 'couvert',
             'controle_ref': str(etranger.pk)},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('controle_ref', r.data)

    def test_mapper_une_exigence_sur_un_controle_reel(self):
        cadre = _cadre(self.company)
        controle = ControleInterne.objects.create(
            company=self.company, code='ACC-01', intitule='Revue')
        r = self._admin().post(
            self.EXIGENCES,
            {'cadre': cadre.pk, 'code_exigence': 'A1', 'intitule': 'X',
             'statut_couverture': 'couvert',
             'controle_ref': str(controle.pk)},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        exigence = ExigenceCadre.objects.get(pk=r.data['id'])
        self.assertEqual(exigence.company, self.company)

    def test_endpoint_couverture(self):
        cadre = _cadre(self.company)
        _exigence(self.company, cadre, 'A1',
                  ExigenceCadre.COUVERTURE_COUVERT, controle_ref='1')
        _exigence(self.company, cadre, 'A2', ExigenceCadre.COUVERTURE_NON)
        r = self._admin().get(f'{self.BASE}{cadre.pk}/couverture/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['taux_pct'], 50.0)

    def test_le_cadre_d_une_autre_societe_est_introuvable(self):
        etranger = _cadre(self.other_company)
        r = self._admin().get(f'{self.BASE}{etranger.pk}/couverture/')
        self.assertEqual(r.status_code, 404)

    def test_liste_scopee_societe(self):
        _cadre(self.other_company)
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
