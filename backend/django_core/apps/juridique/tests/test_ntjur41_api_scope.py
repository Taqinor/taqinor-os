"""NTJUR41 — clé d'API dédiée + scope ``juridique:read``.

Critère d'acceptation : « une clé API SANS le scope ``juridique:read`` reçoit
403 sur tout endpoint ``/api/django/juridique/`` ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.juridique.models import CabinetAvocat, DossierJuridique
from apps.publicapi.constants import (
    ALL_SCOPES, SCOPE_READ_JURIDIQUE, SCOPE_READ_LEADS,
)
from apps.publicapi.models import ApiKey

from ._base import make_company

DOSSIERS = '/api/django/juridique/dossiers/'


def cle(raw):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw}')
    return api


class ScopeJuridiqueTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-a41-co', 'Juridique A41')
        self.autre = make_company('jur-a41-autre', 'Juridique A41 Autre')
        self.dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Contentieux assurable', date_ouverture=date(2026, 5, 1),
            montant_en_jeu=Decimal('250000'), budget_alloue=Decimal('50000'))
        self.secret = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0002',
            titre='Affaire direction', date_ouverture=date(2026, 5, 2),
            confidentialite=(
                DossierJuridique.NiveauConfidentialite.CONFIDENTIEL))
        DossierJuridique.objects.create(
            company=self.autre, reference='JUR-2026-9001',
            titre='Hors société', date_ouverture=date(2026, 5, 3))
        _, self.raw_avec = ApiKey.issue(
            company=self.company, label='Courtier RC',
            scopes=[SCOPE_READ_JURIDIQUE])
        _, self.raw_sans = ApiKey.issue(
            company=self.company, label='Clé leads',
            scopes=[SCOPE_READ_LEADS])

    def test_le_scope_est_bien_au_catalogue(self):
        self.assertIn(SCOPE_READ_JURIDIQUE, ALL_SCOPES)

    def test_sans_le_scope_tout_est_403(self):
        api = cle(self.raw_sans)
        for url in (
            DOSSIERS,
            f'{DOSSIERS}{self.dossier.id}/',
            f'{DOSSIERS}{self.dossier.id}/budget/',
            f'{DOSSIERS}tableau-bord/',
            '/api/django/juridique/mandats/',
            '/api/django/juridique/cabinets-avocats/',
            '/api/django/juridique/audiences/',
            '/api/django/juridique/notes-honoraires/',
        ):
            self.assertEqual(api.get(url).status_code, 403, url)

    def test_avec_le_scope_la_liste_et_le_budget_repondent(self):
        api = cle(self.raw_avec)
        liste = api.get(DOSSIERS)
        self.assertEqual(liste.status_code, 200, liste.data)
        budget = api.get(f'{DOSSIERS}{self.dossier.id}/budget/')
        self.assertEqual(budget.status_code, 200, budget.data)
        self.assertEqual(budget.data['budget_alloue'], '50000.00')

    def test_la_cle_est_scopee_a_sa_societe(self):
        liste = cle(self.raw_avec).get(DOSSIERS)
        references = {row['reference']
                      for row in liste.data.get('results', liste.data)}
        self.assertNotIn('JUR-2026-9001', references)

    def test_une_cle_ne_voit_jamais_un_dossier_confidentiel(self):
        """Une clé n'est jamais un administrateur : le filtrage NTJUR1
        s'applique à l'identique en accès par clé."""
        api = cle(self.raw_avec)
        liste = api.get(DOSSIERS)
        references = {row['reference']
                      for row in liste.data.get('results', liste.data)}
        self.assertIn('JUR-2026-0001', references)
        self.assertNotIn('JUR-2026-0002', references)
        self.assertEqual(
            api.get(f'{DOSSIERS}{self.secret.id}/').status_code, 404)

    def test_la_cle_reste_en_lecture_seule(self):
        api = cle(self.raw_avec)
        cree = api.post(DOSSIERS, {'titre': 'Par la clé',
                                   'date_ouverture': '2026-06-01'},
                        format='json')
        self.assertEqual(cree.status_code, 403, cree.data)
        patch = api.patch(f'{DOSSIERS}{self.dossier.id}/',
                          {'titre': 'Renommé'}, format='json')
        self.assertEqual(patch.status_code, 403)
        self.assertEqual(
            api.delete(f'{DOSSIERS}{self.dossier.id}/').status_code, 403)

    def test_les_autres_actions_restent_hors_de_portee_meme_avec_le_scope(self):
        api = cle(self.raw_avec)
        for url in (f'{DOSSIERS}tableau-bord/',
                    f'{DOSSIERS}export/',
                    f'{DOSSIERS}{self.dossier.id}/timeline/',
                    f'{DOSSIERS}{self.dossier.id}/statuts-suivants/'):
            self.assertEqual(api.get(url).status_code, 403, url)

    def test_une_cle_desactivee_est_rejetee(self):
        instance, raw = ApiKey.issue(
            company=self.company, label='Coupée',
            scopes=[SCOPE_READ_JURIDIQUE])
        instance.enabled = False
        instance.save(update_fields=['enabled'])
        self.assertEqual(cle(raw).get(DOSSIERS).status_code, 401)

    def test_les_surfaces_annexes_restent_fermees_meme_avec_le_scope(self):
        CabinetAvocat.objects.create(company=self.company, nom='Cabinet X')
        api = cle(self.raw_avec)
        for url in ('/api/django/juridique/cabinets-avocats/',
                    '/api/django/juridique/mandats/',
                    '/api/django/juridique/regles-approbation/'):
            self.assertEqual(api.get(url).status_code, 403, url)
