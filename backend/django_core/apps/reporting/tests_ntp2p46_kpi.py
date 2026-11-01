"""NTP2P46 — KPI Procure-to-Pay dans ``apps.reporting``.

Le module est un AGRÉGATEUR pur au-dessus de deux sélecteurs `apps.stock`
déjà testés ailleurs (NTP2P17 ``tableau_bord_achats``, NTP2P19
``conformite_fournisseurs``) : ces tests vérifient donc la COMBINAISON
(moyenne de conformité, champs exposés, garde société) via des doublures,
pas la logique déjà couverte de ces deux sélecteurs.

Couvre :
  * ``dashboard_p2p`` expose le cycle time et les budgets département tels
    que rendus par ``tableau_bord_achats``, sans les altérer ;
  * ``conformite_fournisseur_moyenne`` est la moyenne des scores CONNUS
    (ignore les fournisseurs sans score) et ``None`` sans aucun score
    (jamais un 0 trompeur) ;
  * ``taux_conversion_pct`` (NTP2P47) — % de demandes ``commandee`` parmi
    les demandes DÉCIDÉES (``commandee`` + ``refusee``), via le nouveau
    sélecteur ``apps.installations.selectors.
    comptes_demandes_achat_par_statut`` ; ``None`` (jamais 0/fabriqué) sans
    aucune demande décidée sur la période ;
  * l'endpoint ``GET reporting/p2p/kpi/`` (réservé Responsable/Admin).
"""
import json
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat
from apps.reporting.p2p_kpi import dashboard_p2p
from apps.stock.models import BudgetDepartement
from authentication.models import Company

User = get_user_model()

# AANA45 (PACT10) — contrat partagé avec le vitest du bloc « Achats →
# paiement » : chargé, jamais recopié.
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'kpi_p2p.json')

FAUX_TABLEAU_BORD = {
    'debut': '2026-01-01', 'fin': '2026-01-31',
    'delai_demande_bcf_jours': 3.5,
    'budgets_departement': [
        {'departement': 'Achats', 'taux_consommation_pct': 62.0},
    ],
}


class DashboardP2pTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTP2P46 SA', slug='ntp2p46-sa')

    @patch('apps.stock.selectors.tableau_bord_achats',
           return_value=FAUX_TABLEAU_BORD)
    @patch('apps.stock.selectors.conformite_fournisseurs', return_value=[
        {'fournisseur_id': 1, 'score_risque': 80},
        {'fournisseur_id': 2, 'score_risque': 60},
        {'fournisseur_id': 3, 'score_risque': None},
    ])
    def test_agrege_cycle_time_budgets_et_conformite_moyenne(
            self, _mock_conformite, _mock_tableau):
        resultat = dashboard_p2p(self.company)
        self.assertEqual(resultat['delai_demande_bcf_jours'], 3.5)
        self.assertEqual(resultat['budgets_departement'],
                         FAUX_TABLEAU_BORD['budgets_departement'])
        # (80 + 60) / 2 = 70.0 ; le fournisseur sans score est IGNORÉ.
        self.assertEqual(resultat['conformite_fournisseur_moyenne'], 70.0)

    @patch('apps.stock.selectors.tableau_bord_achats',
           return_value=FAUX_TABLEAU_BORD)
    @patch('apps.stock.selectors.conformite_fournisseurs', return_value=[
        {'fournisseur_id': 1, 'score_risque': None},
    ])
    def test_conformite_moyenne_none_sans_aucun_score(
            self, _mock_conformite, _mock_tableau):
        resultat = dashboard_p2p(self.company)
        self.assertIsNone(resultat['conformite_fournisseur_moyenne'])

    @patch('apps.stock.selectors.tableau_bord_achats',
           return_value=FAUX_TABLEAU_BORD)
    @patch('apps.stock.selectors.conformite_fournisseurs', return_value=[])
    def test_taux_conversion_none_sans_aucune_decision(
            self, _mock_conformite, _mock_tableau):
        resultat = dashboard_p2p(self.company)
        self.assertIsNone(resultat['taux_conversion_pct'])

    @patch('apps.stock.selectors.tableau_bord_achats',
           return_value=FAUX_TABLEAU_BORD)
    @patch('apps.stock.selectors.conformite_fournisseurs', return_value=[])
    def test_taux_conversion_ignore_les_demandes_encore_en_cours(
            self, _mock_conformite, _mock_tableau):
        # NTP2P47 — 3 commandées, 1 refusée, 2 encore en cours (brouillon +
        # soumise) : le taux ne compte QUE les décidées → 3 / (3+1) = 75%.
        DemandeAchat.objects.create(
            company=self.company, reference='DA-C1', objet='x',
            statut=DemandeAchat.Statut.COMMANDEE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-C2', objet='x',
            statut=DemandeAchat.Statut.COMMANDEE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-C3', objet='x',
            statut=DemandeAchat.Statut.COMMANDEE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-R1', objet='x',
            statut=DemandeAchat.Statut.REFUSEE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-B1', objet='x',
            statut=DemandeAchat.Statut.BROUILLON)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-S1', objet='x',
            statut=DemandeAchat.Statut.SOUMISE)

        resultat = dashboard_p2p(self.company)
        self.assertEqual(resultat['taux_conversion_pct'], 75.0)


class KpiP2pEndpointTests(TestCase):
    URL = '/api/django/reporting/p2p/kpi/'

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTP2P46 EP SA', slug='ntp2p46-ep-sa')
        cls.admin = User.objects.create_user(
            username='ntp2p46_admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.normal = User.objects.create_user(
            username='ntp2p46_normal', password='x', company=cls.company,
            role_legacy=User.ROLE_NORMAL)

    def _client_for(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    @patch('apps.stock.selectors.tableau_bord_achats',
           return_value=FAUX_TABLEAU_BORD)
    @patch('apps.stock.selectors.conformite_fournisseurs', return_value=[])
    def test_endpoint_reserve_responsable_admin(
            self, _mock_conformite, _mock_tableau):
        resp = self._client_for(self.admin).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['delai_demande_bcf_jours'], 3.5)

    def test_endpoint_refuse_role_normal(self):
        resp = self._client_for(self.normal).get(self.URL)
        self.assertEqual(resp.status_code, 403)

    def test_utilisateur_sans_societe_400(self):
        sans_societe = User.objects.create_user(
            username='ntp2p46_sans_co', password='x', company=None,
            role_legacy='admin')
        resp = self._client_for(sans_societe).get(self.URL)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('Société requise.', resp.content.decode('utf-8'))

    def test_forme_servie_egale_l_echantillon_partage(self):
        """AANA45 — avec un VRAI budget en base, la réponse porte
        exactement les clés/natures du contrat consommé par l'écran."""
        from django.utils import timezone

        BudgetDepartement.objects.create(
            company=self.company, periodicite='annuelle',
            annee=timezone.localdate().year, mois=0, montant_alloue=100000)
        resp = self._client_for(self.admin).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        servi = json.loads(resp.content)
        attendu = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
        self.assertEqual(set(servi), set(attendu))
        self.assertEqual(len(servi['budgets_departement']), 1)
        budget = servi['budgets_departement'][0]
        modele = attendu['budgets_departement'][0]
        self.assertEqual(set(budget), set(modele))
        for cle, valeur in modele.items():
            self.assertIsInstance(budget[cle], type(valeur), cle)
        # Sans donnée exploitable : null, jamais un 0 inventé.
        self.assertIsNone(servi['delai_demande_bcf_jours'])
        self.assertIsNone(servi['conformite_fournisseur_moyenne'])
        self.assertIsNone(servi['taux_conversion_pct'])
