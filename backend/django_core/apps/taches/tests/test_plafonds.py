"""TCH129 — plafonds de requêtes des routes de F2 (reference/api.md §10 ; `docs/query-budgets.yml`).

Les CIBLES d'api.md §10 (A15, R13) sont les plafonds `assertMaxQueries` ci-dessous ; la CI mesure (un
dépassement donne le compte réel et la liste des requêtes), et la cible devient la mesure au premier
vert. Authentification par le cookie `access_token` : le chemin du navigateur, requêtes
d'authentification comprises, jamais l'en-tête de l'assistant. Chaque route est appelée une fois avant
la mesure (caches du processus chauds : types de contenu, calendrier) : on mesure le régime permanent.
Les listes ne grandissent pas avec leurs lignes (motif 10 → 25 du manifeste) ; l'aperçu de la saisie
rapide est constant en lignes (§10).

Routes de §10 pas encore construites (`tuile/`, `flux/`, `journee/priorites/`, `journee/point/`,
`suggestions/`) : déclarées `enforced: false` dans le manifeste, sans test ici. `saisie-rapide/` est un
POST : le manifeste ne garde que des routes GET (`check_query_budgets._routes_get`), son plafond vit ici.
"""
import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist, Etiquette, EtiquetteTache, Rappel
from apps.taches.tests import fabriques
from core.test_utils import AssertQueryBudgetMixin

URL_AUJOURDHUI = '/api/django/taches/aujourdhui/'
URL_BADGE = '/api/django/taches/badge/'
URL_PROPOSITION = '/api/django/taches/journee/proposition/'
URL_AGENDA = '/api/django/taches/agenda/'
URL_TACHES = '/api/django/taches/taches/'
URL_PROJETS = '/api/django/taches/projets/'
URL_VUE_PROJET = '/api/django/taches/projets/{id}/vue/'
URL_SAISIE = '/api/django/taches/saisie-rapide/'
URL_RYTHME = '/api/django/taches/rythme/'
URL_RECHERCHE = '/api/django/taches/recherche/'


def _peupler(compte, projets, etiquette, jour, nombre, depart=0):
    """`nombre` tâches du jour, à tour de rôle dans `projets`, chacune avec une étiquette, un point de
    check-list, une sous-tâche et un rappel (les relations que lisent ITEM et TACHE) ; autant de tâches
    sans jour dans les projets (candidates de Proposé) ; une tâche À trier."""
    societe = compte.company
    for rang in range(depart, depart + nombre):
        projet = projets[rang % len(projets)]
        tache = fabriques.tache(compte, projet=projet, jour_prevu=jour, titre=f'Devis {rang}', priorite=rang % 4)
        EtiquetteTache.objects.create(company=societe, tache=tache, etiquette=etiquette)
        ElementChecklist.objects.create(company=societe, tache=tache, libelle='Prix', rang=1024)
        fabriques.tache(compte, projet=projet, parent=tache, titre=f'Relire {rang}')
        Rappel.objects.create(company=societe, proprietaire=compte, tache=tache, jour=jour,
                              heure=datetime.time(18, 0))
        fabriques.tache(compte, projet=projet, titre=f'Préparer {rang}', estimation_minutes=30)
    fabriques.tache(compte, titre=f'À trier {depart}')


class PlafondsTests(AssertQueryBudgetMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.jour = timezone.localdate()
        cls.compte = fabriques.compte(fabriques.societe('plafonds'), nom='plafonds')
        fabriques.reglages(cls.compte)
        cls.projets = [fabriques.projet(cls.compte, priorite=priorite) for priorite in (3, 2, 0)]
        fabriques.section(cls.projets[0])
        cls.etiquette = Etiquette.objects.create(company=cls.compte.company, proprietaire=cls.compte, nom='magasin')
        fabriques.activite(cls.compte)
        _peupler(cls.compte, cls.projets, cls.etiquette, cls.jour, 6)

    def setUp(self):
        self.api = APIClient()
        self.api.cookies['access_token'] = str(AccessToken.for_user(self.compte))

    def _lire(self, url):
        reponse = self.api.get(url)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse

    def _erp_dans_journee(self, allume):
        ReglagesRythme.objects.filter(proprietaire=self.compte).update(erp_dans_journee=allume)

    def test_aujourdhui_sans_familles_erp(self):
        self._erp_dans_journee(False)
        self._lire(URL_AUJOURDHUI)
        with self.assertMaxQueries(25):
            self._lire(URL_AUJOURDHUI)

    def test_aujourdhui_avec_familles_erp(self):
        self._erp_dans_journee(True)
        self._lire(URL_AUJOURDHUI)
        with self.assertMaxQueries(31):
            self._lire(URL_AUJOURDHUI)

    def test_badge(self):
        self._lire(URL_BADGE)
        with self.assertMaxQueries(10):
            self._lire(URL_BADGE)

    def test_proposition_du_jour(self):
        self._lire(URL_PROPOSITION)
        with self.assertMaxQueries(20):
            self._lire(URL_PROPOSITION)

    def test_agenda(self):
        self._lire(URL_AGENDA)
        with self.assertMaxQueries(16):
            self._lire(URL_AGENDA)

    def test_liste_des_taches(self):
        self._lire(URL_TACHES)
        with self.assertMaxQueries(12):
            self._lire(URL_TACHES)

    def test_liste_des_projets(self):
        self._lire(URL_PROJETS)
        with self.assertMaxQueries(12):
            self._lire(URL_PROJETS)

    def test_vue_d_un_projet(self):
        url = URL_VUE_PROJET.format(id=self.projets[0].pk)
        self._lire(url)
        with self.assertMaxQueries(15):
            self._lire(url)

    def test_apercu_de_la_saisie_rapide(self):
        corps = {'texte': 'Appeler le fournisseur demain 10 h\nDevis Settat #Ventes\nAcheter des câbles'}
        self.assertEqual(self.api.post(URL_SAISIE, corps, format='json').status_code, 200)
        with self.assertMaxQueries(10):
            reponse = self.api.post(URL_SAISIE, corps, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])

    def test_rythme(self):
        self._lire(URL_RYTHME)
        with self.assertMaxQueries(10):
            self._lire(URL_RYTHME)

    def test_recherche(self):
        url = f'{URL_RECHERCHE}?q=Devis'
        self._lire(url)
        with self.assertMaxQueries(8):
            self._lire(url)


class PlafondsConstantsTests(TestCase):
    """Le nombre de requêtes ne grandit pas avec les lignes (O(1)) : listes et aperçu de la saisie."""

    @classmethod
    def setUpTestData(cls):
        cls.jour = timezone.localdate()
        cls.compte = fabriques.compte(fabriques.societe('plafonds-o1'), nom='plafonds')
        fabriques.reglages(cls.compte)
        cls.projets = [fabriques.projet(cls.compte, priorite=priorite) for priorite in (3, 2)]
        cls.etiquette = Etiquette.objects.create(company=cls.compte.company, proprietaire=cls.compte, nom='magasin')
        _peupler(cls.compte, cls.projets, cls.etiquette, cls.jour, 4)

    def setUp(self):
        self.api = APIClient()
        self.api.cookies['access_token'] = str(AccessToken.for_user(self.compte))

    def _compter(self, appel):
        """Le nombre de requêtes d'`appel()` en régime permanent (un appel de chauffe d'abord)."""
        self.assertEqual(appel().status_code, 200)
        with CaptureQueriesContext(connection) as requetes:
            reponse = appel()
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return len(requetes.captured_queries)

    def test_la_liste_des_taches_ne_grandit_pas(self):
        avant = self._compter(lambda: self.api.get(URL_TACHES))
        _peupler(self.compte, self.projets, self.etiquette, self.jour, 8, depart=100)
        self.assertEqual(self._compter(lambda: self.api.get(URL_TACHES)), avant)

    def test_la_liste_des_projets_ne_grandit_pas(self):
        avant = self._compter(lambda: self.api.get(URL_PROJETS))
        for priorite in (1, 0, 3, 2, 1):
            projet = fabriques.projet(self.compte, priorite=priorite)
            _peupler(self.compte, [projet], self.etiquette, self.jour, 1, depart=200 + priorite)
        self.assertEqual(self._compter(lambda: self.api.get(URL_PROJETS)), avant)

    def test_l_apercu_de_la_saisie_est_constant_en_lignes(self):
        def apercu(lignes):
            texte = '\n'.join(f'Appeler le client {rang} demain' for rang in range(lignes))
            return lambda: self.api.post(URL_SAISIE, {'texte': texte}, format='json')
        self.assertEqual(self._compter(apercu(12)), self._compter(apercu(3)))
