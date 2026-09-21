"""NTDOC19 — Pipeline de renouvellement trimestriel.

Couvre :
  * un contrat expirant dans 45 jours avec un préavis de 60 jours ressort
    « préavis dépassé » ;
  * le pipeline se filtre par trimestre CALENDAIRE (un contrat du trimestre
    suivant n'y est pas) et groupe par mois ;
  * l'avancement de la démarche est DÉRIVÉ de données réelles (alerte
    réellement envoyée, statut `en_negociation`, renouvellement daté,
    résiliation enregistrée) — jamais d'un défaut inventé ;
  * aucune donnée dupliquée avec CONTRAT21 : les exclusions du sélecteur
    d'origine (sans date_fin, résilié, expiré) s'appliquent telles quelles ;
  * un contrat confidentiel ne fuite pas par l'agrégat.

Horloge FIGÉE : ``today`` est injecté dans toutes les assertions.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.contrats import selectors
from apps.contrats.models import AlerteContrat, Contrat, Resiliation

User = get_user_model()

# Mi-trimestre T4 2026 : le pipeline par défaut vise donc octobre→décembre.
AUJOURDHUI = datetime.date(2026, 11, 10)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_admin(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NtDoc19Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc19-a', 'Ntdoc19 A')
        self.co_b = make_company('ntdoc19-b', 'Ntdoc19 B')
        self.admin_a = make_admin(self.co_a, 'ntdoc19-admin-a')
        self.api = auth(self.admin_a)

    def _contrat(self, **kwargs):
        defaults = {
            'company': self.co_a, 'objet': 'Maintenance',
            'statut': Contrat.Statut.ACTIF,
        }
        defaults.update(kwargs)
        return Contrat.objects.create(**defaults)

    def _pipeline(self, **kwargs):
        kwargs.setdefault('today', AUJOURDHUI)
        return selectors.pipeline_renouvellements(self.co_a, **kwargs)


class PreavisDepasseTests(NtDoc19Base):
    def test_echeance_45j_avec_preavis_60j_est_depassee(self):
        """Cas exact du critère d'acceptation."""
        self._contrat(
            reference='CTR-A', date_fin=AUJOURDHUI + datetime.timedelta(days=45),
            preavis_jours=60)
        resultat = self._pipeline()
        self.assertEqual(resultat['total'], 1)
        self.assertEqual(resultat['preavis_depasses'], 1)
        ligne = resultat['mois'][0]['contrats'][0]
        self.assertTrue(ligne['preavis_depasse'])
        self.assertEqual(
            ligne['limite_preavis'],
            AUJOURDHUI + datetime.timedelta(days=45 - 60))

    def test_preavis_encore_ouvert_non_signale(self):
        self._contrat(
            reference='CTR-B', date_fin=AUJOURDHUI + datetime.timedelta(days=45),
            preavis_jours=15)
        resultat = self._pipeline()
        self.assertEqual(resultat['preavis_depasses'], 0)
        self.assertFalse(resultat['mois'][0]['contrats'][0]['preavis_depasse'])

    def test_preavis_deja_traite_non_signale(self):
        self._contrat(
            reference='CTR-C', date_fin=AUJOURDHUI + datetime.timedelta(days=45),
            preavis_jours=60, preavis_traite=True)
        self.assertEqual(self._pipeline()['preavis_depasses'], 0)

    def test_sans_preavis_aucune_urgence_inventee(self):
        self._contrat(
            reference='CTR-D', date_fin=AUJOURDHUI + datetime.timedelta(days=20))
        ligne = self._pipeline()['mois'][0]['contrats'][0]
        self.assertIsNone(ligne['limite_preavis'])
        self.assertFalse(ligne['preavis_depasse'])


class TrimestreTests(NtDoc19Base):
    def test_borne_au_trimestre_calendaire(self):
        dans = self._contrat(reference='CTR-DANS',
                             date_fin=datetime.date(2026, 12, 20))
        self._contrat(reference='CTR-HORS', date_fin=datetime.date(2027, 1, 15))
        resultat = self._pipeline()
        self.assertEqual(resultat['annee'], 2026)
        self.assertEqual(resultat['trimestre'], 4)
        self.assertEqual(resultat['debut'], datetime.date(2026, 10, 1))
        self.assertEqual(resultat['fin'], datetime.date(2026, 12, 31))
        self.assertEqual(resultat['total'], 1)
        self.assertEqual(
            resultat['mois'][0]['contrats'][0]['contrat_id'], dans.pk)

    def test_groupement_par_mois(self):
        self._contrat(reference='CTR-NOV', date_fin=datetime.date(2026, 11, 20))
        self._contrat(reference='CTR-DEC1',
                      date_fin=datetime.date(2026, 12, 5))
        self._contrat(reference='CTR-DEC2',
                      date_fin=datetime.date(2026, 12, 28))
        resultat = self._pipeline()
        self.assertEqual([m['mois'] for m in resultat['mois']], [11, 12])
        self.assertEqual(len(resultat['mois'][1]['contrats']), 2)

    def test_trimestre_passe_renvoie_un_pipeline_vide(self):
        self._contrat(reference='CTR-T1', date_fin=datetime.date(2026, 2, 10))
        resultat = self._pipeline(trimestre=1)
        self.assertEqual(resultat['total'], 0)
        self.assertEqual(resultat['mois'], [])
        self.assertEqual(resultat['preavis_depasses'], 0)

    def test_trimestre_invalide_refuse(self):
        with self.assertRaises(ValueError):
            self._pipeline(trimestre=7)

    def test_exclusions_de_contrat21_preservees(self):
        """Aucune donnée dupliquée : les exclusions CONTRAT21 s'appliquent."""
        self._contrat(reference='CTR-SANS-FIN')  # pas de date_fin
        self._contrat(reference='CTR-RESILIE',
                      date_fin=datetime.date(2026, 12, 1),
                      statut=Contrat.Statut.RESILIE)
        self._contrat(reference='CTR-EXPIRE',
                      date_fin=datetime.date(2026, 12, 2),
                      statut=Contrat.Statut.EXPIRE)
        self.assertEqual(self._pipeline()['total'], 0)


class AvancementTests(NtDoc19Base):
    def test_aucune_action_par_defaut(self):
        self._contrat(reference='CTR-A', date_fin=datetime.date(2026, 12, 1))
        resultat = self._pipeline()
        self.assertEqual(resultat['par_avancement']['aucune_action'], 1)
        self.assertEqual(
            resultat['mois'][0]['contrats'][0]['avancement'], 'aucune_action')

    def test_notifie_quand_une_alerte_a_ete_envoyee(self):
        contrat = self._contrat(reference='CTR-A',
                                date_fin=datetime.date(2026, 12, 1))
        AlerteContrat.objects.create(
            company=self.co_a, contrat=contrat,
            type_alerte=AlerteContrat.TypeAlerte.ECHEANCE,
            date_declenchement=datetime.date(2026, 11, 1),
            statut=AlerteContrat.Statut.ENVOYEE)
        self.assertEqual(
            self._pipeline()['mois'][0]['contrats'][0]['avancement'],
            'notifie')

    def test_alerte_seulement_planifiee_ne_compte_pas(self):
        contrat = self._contrat(reference='CTR-A',
                                date_fin=datetime.date(2026, 12, 1))
        AlerteContrat.objects.create(
            company=self.co_a, contrat=contrat,
            type_alerte=AlerteContrat.TypeAlerte.ECHEANCE,
            date_declenchement=datetime.date(2026, 12, 1),
            statut=AlerteContrat.Statut.PLANIFIEE)
        self.assertEqual(
            self._pipeline()['mois'][0]['contrats'][0]['avancement'],
            'aucune_action')

    def test_en_negociation(self):
        self._contrat(reference='CTR-A', date_fin=datetime.date(2026, 12, 1),
                      statut=Contrat.Statut.EN_NEGOCIATION)
        self.assertEqual(
            self._pipeline()['mois'][0]['contrats'][0]['avancement'],
            'en_negociation')

    def test_renouvele_dans_le_trimestre(self):
        self._contrat(reference='CTR-A', date_fin=datetime.date(2026, 12, 1),
                      date_dernier_renouvellement=datetime.date(2026, 10, 5),
                      nb_renouvellements=1)
        self.assertEqual(
            self._pipeline()['mois'][0]['contrats'][0]['avancement'],
            'renouvele')

    def test_renouvellement_anterieur_au_trimestre_ne_compte_pas(self):
        self._contrat(reference='CTR-A', date_fin=datetime.date(2026, 12, 1),
                      date_dernier_renouvellement=datetime.date(2025, 10, 5),
                      nb_renouvellements=1)
        self.assertEqual(
            self._pipeline()['mois'][0]['contrats'][0]['avancement'],
            'aucune_action')

    def test_resilie_prime_sur_le_reste(self):
        contrat = self._contrat(
            reference='CTR-A', date_fin=datetime.date(2026, 12, 1),
            statut=Contrat.Statut.EN_NEGOCIATION,
            date_dernier_renouvellement=datetime.date(2026, 10, 5))
        Resiliation.objects.create(
            company=self.co_a, contrat=contrat,
            date_demande=datetime.date(2026, 11, 1))
        self.assertEqual(
            self._pipeline()['mois'][0]['contrats'][0]['avancement'],
            'resilie')

    def test_resiliation_annulee_ne_compte_pas(self):
        contrat = self._contrat(reference='CTR-A',
                                date_fin=datetime.date(2026, 12, 1))
        Resiliation.objects.create(
            company=self.co_a, contrat=contrat,
            date_demande=datetime.date(2026, 11, 1),
            statut=Resiliation.Statut.ANNULEE)
        self.assertEqual(
            self._pipeline()['mois'][0]['contrats'][0]['avancement'],
            'aucune_action')


class IsolationTests(NtDoc19Base):
    def test_contrat_d_une_autre_societe_absent(self):
        Contrat.objects.create(
            company=self.co_b, objet='Voisin',
            date_fin=datetime.date(2026, 12, 1),
            statut=Contrat.Statut.ACTIF)
        self.assertEqual(self._pipeline()['total'], 0)

    def test_ids_autorises_restreint_l_agregat(self):
        visible = self._contrat(reference='CTR-VU',
                                date_fin=datetime.date(2026, 12, 1))
        self._contrat(reference='CTR-CACHE',
                      date_fin=datetime.date(2026, 12, 2))
        resultat = self._pipeline(ids_autorises=[visible.pk])
        self.assertEqual(resultat['total'], 1)
        self.assertEqual(
            resultat['mois'][0]['contrats'][0]['contrat_id'], visible.pk)


class ApiPipelineTests(NtDoc19Base):
    URL = '/api/django/contrats/contrats/pipeline-renouvellement/'

    def test_endpoint_repond_la_forme_declaree(self):
        reponse = self.api.get(f'{self.URL}?trimestre=4&annee=2026')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        for cle in ('annee', 'trimestre', 'debut', 'fin', 'total',
                    'preavis_depasses', 'par_avancement', 'mois'):
            self.assertIn(cle, reponse.data)
        self.assertIsInstance(reponse.data['mois'], list)
        self.assertIsInstance(reponse.data['par_avancement'], dict)

    def test_trimestre_invalide_400(self):
        reponse = self.api.get(f'{self.URL}?trimestre=9')
        self.assertEqual(reponse.status_code, 400, reponse.data)

    def test_trimestre_non_numerique_400(self):
        reponse = self.api.get(f'{self.URL}?trimestre=abc')
        self.assertEqual(reponse.status_code, 400, reponse.data)
