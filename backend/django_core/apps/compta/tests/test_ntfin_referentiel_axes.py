"""Tests NTFIN13-19 — Multi-référentiel/multi-GAAP & analytique multi-axes.

Couvre : référentiel principal unique (NTFIN13), écriture multi-livre +
ajustement GAAP isolé du CGNC (NTFIN14/15), axes analytiques configurables
(NTFIN16), imputation multi-axes simultanée (NTFIN17), balance analytique
croisée (NTFIN18), résultat analytique par axe (NTFIN19).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    AxeAnalytique, CentreCout, ImputationAxe, Journal,
    ReferentielComptable,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReferentielTests(TestCase):
    def setUp(self):
        self.company = make_company('ntfin-ref', 'Groupe SA')
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)

    def test_ntfin13_un_seul_principal(self):
        p1 = services.seed_referentiel_principal(self.company)
        p2 = services.seed_referentiel_principal(self.company)
        self.assertEqual(p1.id, p2.id)
        self.assertTrue(p1.est_principal)
        self.assertEqual(
            ReferentielComptable.objects.filter(
                company=self.company, est_principal=True).count(), 1)

    def test_ntfin14_15_ajustement_ifrs_isole_du_cgnc(self):
        principal = services.seed_referentiel_principal(self.company)
        ifrs = ReferentielComptable.objects.create(
            company=self.company, code=ReferentielComptable.Code.IFRS,
            libelle='IFRS', est_principal=False)
        # Écriture CGNC normale (référentiel NULL).
        journal = services._journal(
            self.company, Journal.Type.OPERATIONS_DIVERSES)
        services.creer_ecriture(
            self.company, journal, date(2026, 1, 5), 'CGNC', [
                {'compte': services.get_compte(self.company, '6111'),
                 'debit': Decimal('1000'), 'credit': Decimal('0')},
                {'compte': services.get_compte(self.company, '5141'),
                 'debit': Decimal('0'), 'credit': Decimal('1000')},
            ], statut='validee')
        # Ajustement IFRS (étalement) tagué référentiel IFRS.
        services.poster_ajustement_gaap(
            self.company, ifrs, [
                {'compte': services.get_compte(self.company, '6111'),
                 'debit': Decimal('300'), 'credit': Decimal('0')},
                {'compte': services.get_compte(self.company, '4411'),
                 'debit': Decimal('0'), 'credit': Decimal('300')},
            ], 'Étalement IFRS 16')
        bal_cgnc = selectors.balance_par_referentiel(self.company, principal)
        bal_ifrs = selectors.balance_par_referentiel(self.company, ifrs)
        charge_cgnc = next(
            (li['debit'] for li in bal_cgnc['lignes'] if li['numero'] == '6111'),
            Decimal('0'))
        charge_ifrs = next(
            (li['debit'] for li in bal_ifrs['lignes'] if li['numero'] == '6111'),
            Decimal('0'))
        # La charge CGNC = 1000 (l'ajustement IFRS n'y apparaît pas).
        self.assertEqual(charge_cgnc, Decimal('1000'))
        # Le livre IFRS ne voit QUE son ajustement de 300.
        self.assertEqual(charge_ifrs, Decimal('300'))


class AxesAnalytiquesTests(TestCase):
    def setUp(self):
        self.company = make_company('ntfin-axes', 'Groupe SA')
        self.user = make_user(self.company, 'ntfin-axes-user')
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)
        self.axe_projet = AxeAnalytique.objects.create(
            company=self.company, code='PROJET', libelle='Projet', ordre=1)
        self.axe_region = AxeAnalytique.objects.create(
            company=self.company, code='REGION', libelle='Région', ordre=2)
        self.c_p1 = CentreCout.objects.create(
            company=self.company, code='P1', libelle='Projet 1',
            axe_ref=self.axe_projet)
        self.c_agadir = CentreCout.objects.create(
            company=self.company, code='AGADIR', libelle='Agadir',
            axe_ref=self.axe_region)
        # Une charge de 5000 imputée projet P1 ET région Agadir.
        journal = services._journal(
            self.company, Journal.Type.OPERATIONS_DIVERSES)
        ecr = services.creer_ecriture(
            self.company, journal, date(2026, 2, 1), 'Charge', [
                {'compte': services.get_compte(self.company, '6111'),
                 'debit': Decimal('5000'), 'credit': Decimal('0')},
                {'compte': services.get_compte(self.company, '5141'),
                 'debit': Decimal('0'), 'credit': Decimal('5000')},
            ], statut='validee')
        self.ligne_charge = ecr.lignes.get(compte__numero='6111')
        ImputationAxe.objects.create(
            company=self.company, ligne_ecriture=self.ligne_charge,
            axe=self.axe_projet, centre_cout=self.c_p1)
        ImputationAxe.objects.create(
            company=self.company, ligne_ecriture=self.ligne_charge,
            axe=self.axe_region, centre_cout=self.c_agadir)

    def test_ntfin16_axes_configurables(self):
        self.assertEqual(
            AxeAnalytique.objects.filter(company=self.company).count(), 2)
        self.c_p1.refresh_from_db()
        self.assertEqual(self.c_p1.axe_ref_id, self.axe_projet.id)

    def test_ntfin17_ligne_porte_plusieurs_axes(self):
        self.assertEqual(
            ImputationAxe.objects.filter(
                ligne_ecriture=self.ligne_charge).count(), 2)

    def test_ntfin18_balance_analytique_croisee(self):
        data = selectors.balance_analytique(self.company)
        # La charge remonte sur chacun des 2 axes (projet ET région).
        codes = {(li['axe_code'], li['centre_code']) for li in data['lignes']}
        self.assertIn(('PROJET', 'P1'), codes)
        self.assertIn(('REGION', 'AGADIR'), codes)
        # Filtrage par un seul axe.
        projet = selectors.balance_analytique(self.company, axes=['PROJET'])
        self.assertEqual(len(projet['lignes']), 1)
        self.assertEqual(projet['lignes'][0]['debit'], Decimal('5000'))

    def test_ntfin19_resultat_par_axe(self):
        data = selectors.resultat_par_axe(self.company, 'PROJET')
        self.assertEqual(len(data['valeurs']), 1)
        # Charge 5000 → résultat -5000 sur le projet P1.
        self.assertEqual(data['valeurs'][0]['charges'], Decimal('5000'))
        self.assertEqual(data['total_resultat'], Decimal('-5000'))

    def test_api_axes_crud(self):
        resp = auth(self.user).post(
            '/api/django/compta/axes-analytiques/',
            {'code': 'CANAL', 'libelle': 'Canal', 'ordre': 3}, format='json')
        self.assertEqual(resp.status_code, 201)
        ax = AxeAnalytique.objects.get(id=resp.data['id'])
        self.assertEqual(ax.company_id, self.company.id)
