"""NTDATA15 — exécution & rapport de qualité.

Couvre :
  * `evaluer_regles` persiste un `ResultatQualite` par règle active ;
  * le critère d'acceptation : le rapport rend un TAUX DE CONFORMITÉ par règle ;
  * une règle visant un dataset ABSENT est ignorée (jamais un faux 0 %) ;
  * une population vide rend un taux VIDE, jamais 100 % ;
  * l'historique est conservé (une 2e évaluation ajoute une ligne) ;
  * l'endpoint `/dataquality/rapport/` (avec `?evaluer=1`) et son scoping.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.bi_datasets import CLIENTS_DATASET
from apps.crm.models import Client
from apps.dataquality import services
from apps.dataquality.models import RegleQualite, ResultatQualite
from apps.dataquality.views import RapportQualiteView
from authentication.models import Company

User = get_user_model()

MOTIF_ICE = r'^[0-9]{15}$'


class EvaluerReglesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA15 SA',
                                             slug='ntdata15-sa')
        cls.user = User.objects.create_user(
            username='ntdata15_u', password='x', company=cls.company,
            role_legacy='admin')
        Client.objects.create(company=cls.company, nom='Bon',
                              ice='001234567000089')
        Client.objects.create(company=cls.company, nom='Mauvais', ice='12')

    def _regle(self, **kw):
        defaults = dict(
            company=self.company, libelle='ICE client au bon format',
            entite=CLIENTS_DATASET, champ='ice',
            type_regle=RegleQualite.TypeRegle.FORMAT,
            parametres={'motif': MOTIF_ICE},
            severite=RegleQualite.Severite.BLOQUANT)
        defaults.update(kw)
        return RegleQualite.objects.create(**defaults)

    def test_evaluation_persiste_un_resultat(self):
        regle = self._regle()
        resultats = services.evaluer_regles(self.company, user=self.user)
        self.assertEqual(len(resultats), 1)
        resultat = resultats[0]
        self.assertEqual(resultat.regle_id, regle.id)
        self.assertEqual(resultat.nb_lignes, 2)
        self.assertEqual(resultat.nb_violations, 1)
        self.assertEqual(float(resultat.taux_conformite), 50.0)
        self.assertEqual(resultat.echantillon, [
            Client.objects.get(nom='Mauvais').id])

    def test_rapport_rend_un_taux_par_regle(self):
        self._regle()
        services.evaluer_regles(self.company, user=self.user)
        rapport = services.rapport_qualite(self.company)
        self.assertEqual(len(rapport), 1)
        self.assertEqual(rapport[0]['taux_conformite'], '50.0')
        self.assertEqual(rapport[0]['severite'],
                         RegleQualite.Severite.BLOQUANT)

    def test_regle_jamais_evaluee_apparait_sans_taux(self):
        self._regle()
        rapport = services.rapport_qualite(self.company)
        self.assertIsNone(rapport[0]['taux_conformite'])
        self.assertIsNone(rapport[0]['evalue_le'])

    def test_dataset_absent_est_ignore(self):
        self._regle(entite='dataset_qui_n_existe_pas')
        resultats = services.evaluer_regles(self.company, user=self.user)
        self.assertEqual(resultats, [])

    def test_regle_inactive_non_evaluee(self):
        self._regle(actif=False)
        self.assertEqual(services.evaluer_regles(self.company,
                                                 user=self.user), [])

    def test_population_vide_rend_un_taux_vide(self):
        autre = Company.objects.create(nom='NTDATA15 Vide',
                                       slug='ntdata15-vide')
        RegleQualite.objects.create(
            company=autre, entite=CLIENTS_DATASET, champ='ice',
            type_regle=RegleQualite.TypeRegle.FORMAT,
            parametres={'motif': MOTIF_ICE})
        resultats = services.evaluer_regles(autre, user=None)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0].nb_lignes, 0)
        self.assertIsNone(resultats[0].taux_conformite)

    def test_historique_conserve(self):
        self._regle()
        services.evaluer_regles(self.company, user=self.user)
        services.evaluer_regles(self.company, user=self.user)
        self.assertEqual(
            ResultatQualite.objects.filter(company=self.company).count(), 2)
        # Le rapport ne montre que la DERNIÈRE ligne par règle.
        self.assertEqual(len(services.rapport_qualite(self.company)), 1)

    def test_restriction_par_entite(self):
        self._regle()
        self._regle(entite='ventes_factures', champ='montant_ttc',
                    type_regle=RegleQualite.TypeRegle.PLAGE,
                    parametres={'min': 0})
        self.assertEqual(
            len(services.evaluer_regles(self.company, CLIENTS_DATASET,
                                        user=self.user)), 1)


class RapportEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA15 API',
                                             slug='ntdata15-api')
        cls.responsable = User.objects.create_user(
            username='ntdata15_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata15_simple', password='x', company=cls.company,
            role_legacy='normal')
        Client.objects.create(company=cls.company, nom='Mauvais', ice='12')
        RegleQualite.objects.create(
            company=cls.company, libelle='ICE client au bon format',
            entite=CLIENTS_DATASET, champ='ice',
            type_regle=RegleQualite.TypeRegle.FORMAT,
            parametres={'motif': MOTIF_ICE})

    def _get(self, url, user=None):
        requete = APIRequestFactory().get(url)
        force_authenticate(requete, user=user or self.responsable)
        return RapportQualiteView.as_view()(requete)

    def test_rapport_avec_evaluation_immediate(self):
        reponse = self._get('/api/django/dataquality/rapport/?evaluer=1')
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertEqual(len(reponse.data['regles']), 1)
        self.assertEqual(reponse.data['regles'][0]['taux_conformite'], '0.0')

    def test_filtre_par_entite(self):
        reponse = self._get(
            '/api/django/dataquality/rapport/?entite=ventes_factures')
        self.assertEqual(reponse.data['entite'], 'ventes_factures')
        self.assertEqual(reponse.data['regles'], [])

    def test_utilisateur_non_responsable_refuse(self):
        reponse = self._get('/api/django/dataquality/rapport/',
                            user=self.simple)
        self.assertEqual(reponse.status_code, status.HTTP_403_FORBIDDEN)


class JobQualiteTests(TestCase):
    def test_job_balaye_les_societes_actives(self):
        from apps.dataquality.tasks import evaluer_qualite_donnees

        company = Company.objects.create(nom='NTDATA15 Job',
                                         slug='ntdata15-job')
        Client.objects.create(company=company, nom='Mauvais', ice='12')
        RegleQualite.objects.create(
            company=company, entite=CLIENTS_DATASET, champ='ice',
            type_regle=RegleQualite.TypeRegle.FORMAT,
            parametres={'motif': MOTIF_ICE})
        recap = evaluer_qualite_donnees()
        lignes = {entree['company']: entree['nb_regles'] for entree in recap}
        self.assertEqual(lignes.get(company.pk), 1)
        self.assertTrue(
            ResultatQualite.objects.filter(company=company).exists())
