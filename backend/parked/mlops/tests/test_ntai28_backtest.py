"""NTAI28 — Backtesting des scorers (évaluation sur historique).

Couvre :
  * ``backtester(company, 'win_proba')`` calcule des métriques cohérentes sur
    un jeu de leads SIGNÉS/PERDUS (scopé société), déterministe ;
  * un lead à issue encore inconnue (ni signé ni perdu) n'entre PAS dans
    l'échantillon ;
  * sans aucun lead à issue connue → ``disponible: False`` (jamais une
    métrique inventée) ;
  * ``retard_paiement`` renvoie ``disponible: False`` avec un motif explicite
    (aucune date de paiement réelle accessible) — jamais un chiffre fabriqué ;
  * un nom de scorer inconnu lève ``ValueError`` ;
  * l'endpoint ``GET mlops/backtests/`` (réservé Responsable/Admin).
"""
import datetime

from django.utils import timezone

from authentication.models import CustomUser
from testkit.base import TenantAPITestCase

from apps.crm import stages as crm_stages
from apps.crm.models import Lead
from apps.mlops.backtest import backtester


class BacktestWinProbaTests(TenantAPITestCase):
    def _lead(self, *, signe=False, perdu=False, canal='site',
              priorite='haute', company=None):
        stage = crm_stages.SIGNED if signe else crm_stages.NEW
        return Lead.objects.create(
            company=company or self.company, nom='Lead test', stage=stage,
            perdu=perdu, canal=canal, priorite=priorite)

    def test_metriques_deterministes_sur_jeu_connu(self):
        # canal/priorité choisis pour bien SÉPARER les deux classes : le
        # scorer, privé de stage/perdu (voir docstring de backtest.py), ne
        # module son score que par canal × priorité — un seuil intermédiaire
        # (0.1) sépare donc parfaitement ce jeu construit.
        self._lead(signe=True, canal='recommandation', priorite='haute')
        self._lead(signe=True, canal='recommandation', priorite='haute')
        self._lead(signe=False, perdu=True, canal='achat', priorite='basse')
        self._lead(signe=False, perdu=True, canal='achat', priorite='basse')

        resultat = backtester(self.company, 'win_proba', seuil=0.1)
        self.assertTrue(resultat['disponible'])
        self.assertEqual(resultat['taille_echantillon'], 4)
        self.assertEqual(resultat['precision'], 1.0)
        self.assertEqual(resultat['rappel'], 1.0)
        self.assertEqual(resultat['auc'], 1.0)
        # Déterministe : un second appel sur le même jeu renvoie EXACTEMENT
        # les mêmes métriques.
        self.assertEqual(
            resultat, backtester(self.company, 'win_proba', seuil=0.1))

    def test_lead_en_cours_exclu_de_lechantillon(self):
        self._lead(signe=True)
        self._lead(signe=False, perdu=False)  # encore en cours : exclu.
        resultat = backtester(self.company, 'win_proba')
        self.assertEqual(resultat['taille_echantillon'], 1)

    def test_sans_issue_connue_indisponible(self):
        self._lead(signe=False, perdu=False)
        resultat = backtester(self.company, 'win_proba')
        self.assertFalse(resultat['disponible'])
        self.assertIn('motif', resultat)

    def test_filtre_periode_sur_mois_creation(self):
        ancien = self._lead(signe=True)
        Lead.objects.filter(pk=ancien.pk).update(
            date_creation=timezone.make_aware(
                datetime.datetime(2020, 1, 15)))
        self._lead(signe=True)  # créé ce mois-ci.

        debut_mois_courant = timezone.now().date().replace(day=1)
        resultat = backtester(
            self.company, 'win_proba', periode=(debut_mois_courant, None))
        self.assertEqual(resultat['taille_echantillon'], 1)

    def test_isolation_societe(self):
        self._lead(signe=True, company=self.other_company)
        resultat = backtester(self.company, 'win_proba')
        self.assertFalse(resultat['disponible'])

    def test_retard_paiement_indisponible_jamais_invente(self):
        resultat = backtester(self.company, 'retard_paiement')
        self.assertFalse(resultat['disponible'])
        self.assertIn('motif', resultat)
        self.assertNotIn('precision', resultat)

    def test_scorer_inconnu_leve(self):
        with self.assertRaises(ValueError):
            backtester(self.company, 'scorer_qui_nexiste_pas')


class BacktestEndpointTests(TenantAPITestCase):
    URL = '/api/django/mlops/backtests/'

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_endpoint_win_proba(self):
        Lead.objects.create(
            company=self.company, nom='Lead', stage=crm_stages.SIGNED,
            perdu=False, canal='site', priorite='haute')
        resp = self._admin().get(self.URL, {'nom': 'win_proba'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['disponible'])

    def test_endpoint_nom_invalide(self):
        resp = self._admin().get(self.URL, {'nom': 'nawak'})
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_non_admin_refuse(self):
        resp = self.client_as().get(self.URL, {'nom': 'win_proba'})
        self.assertEqual(resp.status_code, 403)
