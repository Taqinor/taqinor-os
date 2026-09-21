"""NTESG19 — codes d'indicateurs proposables pour un objectif de trajectoire.

Ce que le test PROUVE :
  * seuls les codes d'indicateurs RÉELS de la société sont proposés — un code
    inventé produirait un objectif dont le « réalisé » resterait vide ;
  * chaque code porte les années cibles DÉJÀ prises par un objectif ACTIF :
    c'est ce qui permet à l'assistant de refuser le doublon avant l'appel ;
  * un objectif INACTIF ne bloque pas son année (il est désactivé) ;
  * cross-tenant : les indicateurs et objectifs d'une autre société n'y
    apparaissent jamais ;
  * la contrainte d'unicité reste la barrière FINALE côté serveur (400).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.esg import selectors
from apps.esg.models import ObjectifESGTrajectoire
from authentication.models import Company

User = get_user_model()

URL = '/api/django/esg/objectifs-esg/codes-disponibles/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _indicateur(company, code, libelle, pilier='environnement'):
    from apps.qhse.models import IndicateurESG
    return IndicateurESG.objects.create(
        company=company, code=code, libelle=libelle, pilier=pilier,
        annee=2026, valeur=Decimal('100'), unite='tCO2e')


class CodesIndicateursDisponiblesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ESG Co', slug='esg-ntesg19')
        self.user = User.objects.create_user(
            username='ntesg19-user', password='x', company=self.co,
            role_legacy='responsable')

    def test_liste_vide_sans_indicateur(self):
        self.assertEqual(selectors.codes_indicateurs_disponibles(self.co), [])

    def test_codes_reels_proposes(self):
        _indicateur(self.co, 'ENV-CO2', 'Émissions de CO2')
        _indicateur(self.co, 'SOC-FORM', 'Heures de formation',
                    pilier='social')
        codes = selectors.codes_indicateurs_disponibles(self.co)
        self.assertEqual(
            [c['code'] for c in codes], ['ENV-CO2', 'SOC-FORM'])
        self.assertEqual(codes[0]['libelle'], 'Émissions de CO2')
        self.assertEqual(codes[0]['objectifs_actifs'], [])

    def test_annees_cibles_deja_prises(self):
        _indicateur(self.co, 'ENV-CO2', 'Émissions de CO2')
        for annee in (2030, 2027):
            ObjectifESGTrajectoire.objects.create(
                company=self.co, indicateur_code='ENV-CO2',
                valeur_reference=Decimal('100'), annee_reference=2024,
                valeur_cible=Decimal('50'), annee_cible=annee, actif=True)
        codes = selectors.codes_indicateurs_disponibles(self.co)
        self.assertEqual(codes[0]['objectifs_actifs'], [2027, 2030])

    def test_objectif_inactif_ne_bloque_pas_l_annee(self):
        _indicateur(self.co, 'ENV-CO2', 'Émissions de CO2')
        ObjectifESGTrajectoire.objects.create(
            company=self.co, indicateur_code='ENV-CO2',
            valeur_reference=Decimal('100'), annee_reference=2024,
            valeur_cible=Decimal('50'), annee_cible=2030, actif=False)
        codes = selectors.codes_indicateurs_disponibles(self.co)
        self.assertEqual(codes[0]['objectifs_actifs'], [])

    def test_endpoint(self):
        _indicateur(self.co, 'ENV-CO2', 'Émissions de CO2')
        resp = _api(self.user).get(URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(len(resp.data), 1)
        for cle in ('code', 'libelle', 'pilier', 'unite', 'objectifs_actifs'):
            self.assertIn(cle, resp.data[0])

    def test_cross_tenant(self):
        autre = Company.objects.create(nom='Autre', slug='esg-ntesg19-autre')
        _indicateur(autre, 'SECRET', 'Chez le voisin')
        _indicateur(self.co, 'ENV-CO2', 'Émissions de CO2')
        codes = [c['code']
                 for c in selectors.codes_indicateurs_disponibles(self.co)]
        self.assertEqual(codes, ['ENV-CO2'])

    def test_unicite_reste_la_barriere_finale(self):
        """L'écran refuse d'abord ; le serveur refuse TOUJOURS (course perdue)."""
        _indicateur(self.co, 'ENV-CO2', 'Émissions de CO2')
        ObjectifESGTrajectoire.objects.create(
            company=self.co, indicateur_code='ENV-CO2',
            valeur_reference=Decimal('100'), annee_reference=2024,
            valeur_cible=Decimal('50'), annee_cible=2030, actif=True)
        resp = _api(self.user).post('/api/django/esg/objectifs-esg/', {
            'indicateur_code': 'ENV-CO2', 'valeur_reference': 90,
            'annee_reference': 2025, 'valeur_cible': 40, 'annee_cible': 2030,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('indicateur_code', resp.data)
