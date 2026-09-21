"""NTDATA16 — tableau de complétude par module.

Couvre :
  * le critère d'acceptation : un client SANS ICE/adresse fait BAISSER le
    score de complétude « clients » ;
  * le détail champ par champ ;
  * une entité sans fiche rend un score VIDE, jamais 100 % ;
  * le scoping société ;
  * l'endpoint `/dataquality/completude/`.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.models import Client
from apps.dataquality import selectors
from apps.dataquality.views import CompletudeView
from authentication.models import Company

User = get_user_model()


class CompletudeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA16 SA',
                                             slug='ntdata16-sa')
        cls.autre = Company.objects.create(nom='NTDATA16 Autre',
                                           slug='ntdata16-autre')
        cls.user = User.objects.create_user(
            username='ntdata16_u', password='x', company=cls.company,
            role_legacy='admin')

    def _client_complet(self, nom='Complet'):
        return Client.objects.create(
            company=self.company, nom=nom, telephone='0600000001',
            adresse='12 rue X, Casablanca', ice='001234567000089')

    def test_client_complet_score_plein(self):
        self._client_complet()
        mesure = selectors.completude_entite(self.company, self.user,
                                             'clients')
        self.assertEqual(mesure['nb_lignes'], 1)
        self.assertEqual(mesure['score_pct'], 100.0)

    def test_client_sans_ice_ni_adresse_fait_baisser_le_score(self):
        self._client_complet()
        Client.objects.create(company=self.company, nom='Partiel',
                              telephone='0600000002')
        mesure = selectors.completude_entite(self.company, self.user,
                                             'clients')
        # 8 cellules critiques (2 fiches × 4 champs), 6 remplies ⇒ 75 %.
        self.assertEqual(mesure['nb_lignes'], 2)
        self.assertEqual(mesure['score_pct'], 75.0)
        self.assertEqual(mesure['par_champ']['ice'], 50.0)
        self.assertEqual(mesure['par_champ']['adresse'], 50.0)
        self.assertEqual(mesure['par_champ']['nom'], 100.0)

    def test_entite_sans_fiche_score_vide(self):
        mesure = selectors.completude_entite(self.company, self.user,
                                             'clients')
        self.assertEqual(mesure['nb_lignes'], 0)
        self.assertIsNone(mesure['score_pct'])

    def test_scoping_societe(self):
        Client.objects.create(company=self.autre, nom='Ailleurs')
        self._client_complet()
        mesure = selectors.completude_entite(self.company, self.user,
                                             'clients')
        self.assertEqual(mesure['nb_lignes'], 1)

    def test_entite_inconnue(self):
        self.assertIsNone(
            selectors.completude_entite(self.company, self.user, 'inexistant'))

    def test_tableau_complet_et_score_global(self):
        self._client_complet()
        tableau = selectors.completude_module(self.company, self.user)
        cles = {e['entite'] for e in tableau['entites']}
        self.assertEqual(cles, set(selectors.CHAMPS_CRITIQUES))
        # Seule l'entité « clients » a des fiches : la moyenne ne porte que
        # sur elle (les entités vides n'entrent pas dans le calcul).
        self.assertEqual(tableau['score_global'], 100.0)

    def test_aucune_fiche_du_tout_score_global_vide(self):
        tableau = selectors.completude_module(self.company, self.user)
        self.assertIsNone(tableau['score_global'])


class CompletudeEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA16 API',
                                             slug='ntdata16-api')
        cls.responsable = User.objects.create_user(
            username='ntdata16_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata16_simple', password='x', company=cls.company,
            role_legacy='normal')
        Client.objects.create(company=cls.company, nom='Partiel')

    def _get(self, user=None):
        requete = APIRequestFactory().get(
            '/api/django/dataquality/completude/')
        force_authenticate(requete, user=user or self.responsable)
        return CompletudeView.as_view()(requete)

    def test_endpoint(self):
        reponse = self._get()
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        clients = next(e for e in reponse.data['entites']
                       if e['entite'] == 'clients')
        self.assertEqual(clients['nb_lignes'], 1)
        self.assertEqual(clients['score_pct'], 25.0)

    def test_utilisateur_non_responsable_refuse(self):
        self.assertEqual(self._get(user=self.simple).status_code,
                         status.HTTP_403_FORBIDDEN)
