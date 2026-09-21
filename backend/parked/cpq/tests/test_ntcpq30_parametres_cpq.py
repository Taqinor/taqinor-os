"""NTCPQ30 — Écran Paramètres « CPQ » par société : singleton REST.

Couvre :
* GET/PATCH ``cpq/parametres-cpq/courant/`` (get_or_create, company posée
  serveur, écriture réservée Directeur/Commercial responsable) ;
* ``approbation_active=False`` fait passer ``envoyer``/``generer-pdf`` en
  direct SANS blocage NTCPQ7 pour la société concernée, SANS affecter une
  autre société (isolation multi-tenant du réglage).
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq import services
from apps.cpq.models import (
    ParametresCPQ, RegleApprobationRemise, EtapeApprobationDevis,
)
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, DevisFactory, UserFactory

PARAMETRES = '/api/django/cpq/parametres-cpq/courant/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestParametresCpqSingleton(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)

    def test_courant_get_or_create(self):
        resp = auth(self.admin).get(PARAMETRES)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['approbation_active'])
        self.assertEqual(ParametresCPQ.objects.filter(
            company=self.company).count(), 1)

    def test_patch_reserve_responsable(self):
        resp = auth(self.normal).patch(
            PARAMETRES, {'approbation_active': False}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_patch_desactive_approbation(self):
        resp = auth(self.admin).patch(
            PARAMETRES, {'approbation_active': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['approbation_active'])
        parametres = ParametresCPQ.objects.get(company=self.company)
        self.assertFalse(parametres.approbation_active)


class TestApprobationActiveGating(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other_company = CompanyFactory()
        # Palier d'approbation couvrant TOUTE remise (≥0 %) → toute remise
        # positive déclenche normalement une étape.
        RegleApprobationRemise.objects.create(
            company=self.company, remise_min_pct=Decimal('0'),
            remise_max_pct=Decimal('100'), nombre_approbateurs=1)
        RegleApprobationRemise.objects.create(
            company=self.other_company, remise_min_pct=Decimal('0'),
            remise_max_pct=Decimal('100'), nombre_approbateurs=1)

    def test_approbation_active_par_defaut(self):
        devis = DevisFactory(company=self.company, remise_globale=Decimal('10'))
        etapes = services.lancer_approbation_devis(devis)
        self.assertEqual(len(etapes), 1)
        self.assertEqual(
            EtapeApprobationDevis.objects.filter(devis=devis).count(), 1)

    def test_approbation_desactivee_envoi_direct(self):
        ParametresCPQ.objects.create(
            company=self.company, approbation_active=False)
        devis = DevisFactory(company=self.company, remise_globale=Decimal('10'))
        etapes = services.lancer_approbation_devis(devis)
        self.assertEqual(etapes, [])
        self.assertEqual(
            EtapeApprobationDevis.objects.filter(devis=devis).count(), 0)

    def test_desactivation_scopee_a_une_seule_societe(self):
        ParametresCPQ.objects.create(
            company=self.company, approbation_active=False)
        # La société A n'a plus d'approbation…
        devis_a = DevisFactory(company=self.company, remise_globale=Decimal('10'))
        self.assertEqual(services.lancer_approbation_devis(devis_a), [])
        # …mais la société B (aucun réglage) garde le comportement historique.
        devis_b = DevisFactory(
            company=self.other_company, remise_globale=Decimal('10'))
        etapes_b = services.lancer_approbation_devis(devis_b)
        self.assertEqual(len(etapes_b), 1)
