"""NTAI23 — Coaching commercial agrégé (talk-ratio, objections, sentiment).

Couvre :
  * les objections/produits les plus fréquents sont bien comptés sur les
    appels ANALYSÉS uniquement (un appel non analysé n'entre dans aucun
    total) ;
  * le sentiment moyen global est une proportion de « positif », ``None``
    sans aucun appel analysé (jamais un 0 trompeur) ;
  * le découpage « par_commercial » vient du ``owner`` du lead rattaché à
    l'appel — un appel sans lead (ou dont le lead n'a pas de owner) n'entre
    dans AUCUN groupe ;
  * le filtre ``periode`` restreint sur la date d'analyse ;
  * l'isolation société (endpoint + sélecteur) ;
  * l'endpoint ``GET appels/synthese/``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from authentication.models import Company

from ..models import AppelCommercial
from ..selectors import synthese_appels

User = get_user_model()

URL = '/api/django/conversation_ai/appels/synthese/'


class SyntheseAppelsSelectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTAI23 SA', slug='ntai23-sa')
        cls.autre = Company.objects.create(
            nom='NTAI23 Autre', slug='ntai23-autre')
        cls.commercial = User.objects.create_user(
            username='ntai23_commercial', password='x', company=cls.company,
            role_legacy='commercial')

    def _appel(self, *, objections=None, produits=None, sentiment='neutre',
               lead=None, analyse_le=None, company=None):
        appel = AppelCommercial.objects.create(
            company=company or self.company, lead=lead,
            statut=AppelCommercial.STATUT_TRANSCRIT,
            transcript='texte', sentiment=sentiment,
            analyse_json={
                'objections': objections or [],
                'next_steps': [],
                'produits': produits or [],
                'sentiment': sentiment,
            },
            analyse_le=analyse_le or timezone.now())
        return appel

    def test_objections_et_produits_comptes_sur_analyses_seulement(self):
        self._appel(objections=['prix trop élevé'], produits=['onduleur'])
        self._appel(objections=['prix trop élevé'], produits=['batterie'])
        # Non analysé : ne doit compter nulle part.
        AppelCommercial.objects.create(
            company=self.company, statut=AppelCommercial.STATUT_TRANSCRIT,
            transcript='x', analyse_json={'objections': ['ignoré']})

        resultat = synthese_appels(self.company)
        self.assertEqual(resultat['nb_appels_analyses'], 2)
        self.assertEqual(resultat['top_objections'][0],
                         {'objection': 'prix trop élevé', 'nb': 2})
        noms_produits = {p['produit'] for p in resultat['produits_cites']}
        self.assertEqual(noms_produits, {'onduleur', 'batterie'})

    def test_sentiment_moyen_global_none_sans_appel(self):
        self.assertIsNone(
            synthese_appels(self.company)['sentiment_moyen_global'])

    def test_sentiment_moyen_global_proportion_positif(self):
        self._appel(sentiment='positif')
        self._appel(sentiment='positif')
        self._appel(sentiment='negatif')
        self._appel(sentiment='neutre')
        resultat = synthese_appels(self.company)
        self.assertEqual(resultat['sentiment_moyen_global'], 0.5)

    def test_par_commercial_vient_du_owner_du_lead(self):
        lead = Lead.objects.create(
            company=self.company, nom='Client X', owner=self.commercial)
        self._appel(lead=lead, sentiment='positif')
        self._appel(lead=lead, sentiment='negatif')
        # Appel sans lead : n'entre dans aucun groupe « par_commercial ».
        self._appel(sentiment='positif')

        resultat = synthese_appels(self.company)
        self.assertEqual(len(resultat['par_commercial']), 1)
        groupe = resultat['par_commercial'][0]
        self.assertEqual(groupe['commercial'], 'ntai23_commercial')
        self.assertEqual(groupe['nb_appels'], 2)
        self.assertEqual(groupe['sentiment_positif_pct'], 50.0)

    def test_lead_sans_owner_exclu_du_decoupage(self):
        lead_sans_owner = Lead.objects.create(
            company=self.company, nom='Client Y')
        self._appel(lead=lead_sans_owner, sentiment='positif')
        resultat = synthese_appels(self.company)
        self.assertEqual(resultat['par_commercial'], [])
        # L'appel compte quand même dans les totaux globaux.
        self.assertEqual(resultat['nb_appels_analyses'], 1)

    def test_filtre_periode_sur_date_analyse(self):
        ancien = timezone.now() - timezone.timedelta(days=40)
        self._appel(objections=['ancien'], analyse_le=ancien)
        self._appel(objections=['recent'])

        resultat = synthese_appels(
            self.company,
            periode=(timezone.now().date() - timezone.timedelta(days=1),
                     None))
        self.assertEqual(resultat['nb_appels_analyses'], 1)
        self.assertEqual(
            resultat['top_objections'][0]['objection'], 'recent')

    def test_isolation_societe(self):
        self._appel(objections=['fuite ?'], company=self.autre)
        resultat = synthese_appels(self.company)
        self.assertEqual(resultat['nb_appels_analyses'], 0)


class SyntheseAppelsEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='NTAI23 EP SA', slug='ntai23-ep-sa')
        cls.user = User.objects.create_user(
            username='ntai23_ep_u', password='x', company=cls.company,
            role_legacy='admin')

    def _auth(self):
        client = APIClient()
        token = AccessToken.for_user(self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client

    def test_endpoint_renvoie_la_synthese(self):
        AppelCommercial.objects.create(
            company=self.company, statut=AppelCommercial.STATUT_TRANSCRIT,
            transcript='texte', sentiment='positif',
            analyse_json={'objections': ['délai'], 'produits': [],
                          'next_steps': [], 'sentiment': 'positif'},
            analyse_le=timezone.now())
        resp = self._auth().get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_appels_analyses'], 1)
        self.assertEqual(
            resp.data['top_objections'][0]['objection'], 'délai')
