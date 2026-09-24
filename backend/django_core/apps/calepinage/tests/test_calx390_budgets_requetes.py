"""CALX390 — les budgets de requêtes SQL du module calepinage.

``docs/query-budgets.yml`` est le contrat de perf par endpoint, rendu
opposable par ``scripts/check_query_budgets.py`` (un endpoint
``enforced: true`` sans test de budget qui référence son URL fait rougir le
job ``stage-names``). Ce fichier est CE test pour les trois endpoints du
module :

* ``/api/django/calepinage/calepinages/`` — la liste (``layout_stale`` /
  ``layout_nb_panneaux`` lus, ligne par ligne, sur le devis lié et ses
  lignes) ;
* ``/api/django/calepinage/calepinages/<pk>/`` — le détail agrégé (lead,
  client, devis, compteurs de versions et de variantes, contexte
  géographique, droits) ;
* ``/api/django/calepinage/calepinages/<pk>/resultat/`` — le résultat servi
  (pose, électrique, simulation persistée, fraîcheur).

Patron de la maison (``apps/crm/tests_yopsb13_lead_query_budget.py``) : le
compte est mesuré à 10 puis à 25 objets et ne doit PAS bouger (O(1), pas
O(n)), puis borné par le plafond ÉCRIT dans le manifeste — lu ICI dans
``docs/query-budgets.yml``, jamais recopié, pour que le test et le contrat ne
puissent pas diverger. Un témoin prouve que la garde MORD : sans le
``prefetch_related('devis__lignes')`` du chemin de la liste, le compte grandit
avec les lignes. (Sans le seul ``select_related('devis')``, ce même prefetch
charge les devis en UNE requête : le compte ne grandit pas, il prend une
requête de plus — c'est le plafond qui le voit.)

Le compte est pris en régime PERMANENT : une première requête « à blanc »
chauffe les caches de processus (types de contenu, réglages), comme le fait
YOPSB13 — sans elle, le premier appel porterait une requête unique que le
second n'a plus, et simulerait une croissance.

Run :
    python manage.py test apps.calepinage.tests.test_calx390_budgets_requetes -v2
"""
import pathlib
import re
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.variantes import creer_variante
from apps.calepinage.views.calepinages import CalepinageViewSet
from apps.ventes.models import Devis, LigneDevis
from core.test_utils import AssertQueryBudgetMixin

from .test_api_liste import BaseApiCalepinage

#: Les trois chemins, ÉCRITS tels que le manifeste les déclare (la garde
#: ``check_query_budgets.py`` cherche ces chaînes dans ce fichier).
LISTE = '/api/django/calepinage/calepinages/'
DETAIL = '/api/django/calepinage/calepinages/<pk>/'
RESULTAT = '/api/django/calepinage/calepinages/<pk>/resultat/'

#: Un document de pose minimal (schéma v2) : deux pans posés.
LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}},
        {'id': 'b', 'label': 'PAN-B',
         'geometry': {'count': 7, 'azimuthDeg': 90.0, 'tiltDeg': 15.0}},
    ],
}


def _manifeste():
    ici = pathlib.Path(__file__).resolve()
    for parent in ici.parents:
        candidat = parent / 'docs' / 'query-budgets.yml'
        if candidat.exists():
            return candidat.read_text(encoding='utf-8')
    raise AssertionError('docs/query-budgets.yml introuvable — le contrat de '
                         'perf par endpoint.')


def budget_du_manifeste(chemin):
    """Le plafond ÉCRIT dans le manifeste pour ``chemin`` — et ``enforced``."""
    motif = re.compile(
        r'-\s+path:\s*' + re.escape(chemin) + r'\s*\n'
        r'\s+budget:\s*(\d+)\s*\n'
        r'\s+enforced:\s*(true|false)')
    trouve = motif.search(_manifeste())
    if trouve is None:
        raise AssertionError('Aucune entrée « %s » dans docs/query-budgets.yml '
                             '(path, budget, enforced — dans cet ordre).'
                             % chemin)
    return int(trouve.group(1)), trouve.group(2) == 'true'


def _url(modele, pk):
    return modele.replace('<pk>', str(pk))


class BudgetsRequetesCalepinageEnBaseTest(
        AssertQueryBudgetMixin, BaseApiCalepinage):
    """Les trois endpoints : O(1) en lignes, et sous le plafond du manifeste."""

    def setUp(self):
        super().setUp()
        from django.contrib.contenttypes.models import ContentType

        # Caches de processus chauffés AVANT toute mesure (voir l'en-tête).
        ContentType.objects.get_for_model(Calepinage)
        self._rang = 0

    # ── Fabrique ───────────────────────────────────────────────────────────
    def _devis(self):
        """Un devis de la société AVEC une ligne panneau : la péremption la
        lit, c'est donc elle qui doit être chargée d'avance par la liste."""
        self._rang += 1
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='CALX390-%04d' % self._rang, roof_layout=LAYOUT)
        LigneDevis.objects.create(
            devis=devis, designation='Panneau photovoltaïque 710 Wc',
            quantite=Decimal('19'), prix_unitaire=Decimal('1000'))
        return devis

    def _semer_liste(self, nombre):
        for _ in range(nombre):
            Calepinage.objects.create(
                company=self.company, lead_id=self.lead.pk,
                devis=self._devis(), titre='Toiture %d' % self._rang,
                roof_layout=LAYOUT, layout_hash='a' * 64)

    def _pivot(self):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            devis=self._devis(), titre='Pivot', roof_layout=LAYOUT,
            layout_hash='b' * 64)

    def _semer_lignes_du_pivot(self, pivot, nombre):
        """Les lignes LIÉES qu'un détail agrège : versions et variantes."""
        for _ in range(nombre):
            self._rang += 1
            CalepinageVersion.objects.create(
                company=self.company, calepinage=pivot,
                libelle='Version %d' % self._rang, roof_layout=LAYOUT,
                layout_hash='c' * 64)
            creer_variante(pivot, nom='Variante %d' % self._rang,
                           roof_layout=LAYOUT, resultat={'kwc': 8.6})

    def _compte(self, url):
        with CaptureQueriesContext(connection) as capture:
            reponse = self.api.get(url)
        self.assertEqual(reponse.status_code, 200, getattr(reponse, 'data',
                                                           None))
        return len(capture.captured_queries), reponse

    def _nombre_de_lignes(self, reponse):
        donnees = reponse.data
        return len(donnees['results'] if isinstance(donnees, dict)
                   and 'results' in donnees else donnees)

    # ── La liste ───────────────────────────────────────────────────────────
    def _croissance_liste(self):
        self._compte(LISTE)  # à blanc : régime permanent
        self._semer_liste(10)
        a_10, reponse = self._compte(LISTE)
        self.assertEqual(self._nombre_de_lignes(reponse), 10)
        self._semer_liste(15)
        a_25, reponse = self._compte(LISTE)
        self.assertEqual(self._nombre_de_lignes(reponse), 25)
        return a_10, a_25

    def test_la_liste_ne_grandit_pas_avec_les_lignes(self):
        a_10, a_25 = self._croissance_liste()
        self.assertEqual(
            a_10, a_25,
            'GET %s : %d requêtes à 10 lignes, %d à 25 — N+1. Vérifier le '
            "select_related('client', 'devis') du viewset et le "
            "prefetch_related('devis__lignes') de sa liste." % (
                LISTE, a_10, a_25))
        budget, gardee = budget_du_manifeste(LISTE)
        self.assertTrue(gardee)
        self.assertLessEqual(
            a_25, budget,
            'GET %s : %d requêtes mesurées, plafond %d dans '
            'docs/query-budgets.yml.' % (LISTE, a_25, budget))

    def test_la_liste_tient_son_plafond(self):
        budget, _gardee = budget_du_manifeste(LISTE)
        self._compte(LISTE)
        self._semer_liste(10)
        with self.assertMaxQueries(budget):
            reponse = self.api.get(LISTE)
        self.assertEqual(reponse.status_code, 200)

    def test_la_garde_mord_sans_le_prefetch_des_lignes(self):
        """Témoin : sans ``prefetch_related('devis__lignes')``, ça grandit."""
        def sans_prefetch(vue, queryset):
            return super(CalepinageViewSet, vue).filter_queryset(queryset)

        with mock.patch.object(CalepinageViewSet, 'filter_queryset',
                               sans_prefetch):
            a_10, a_25 = self._croissance_liste()
        self.assertGreater(a_25, a_10)

    # ── Le détail agrégé et le résultat servi ──────────────────────────────
    def _croissance_du_pivot(self, modele):
        pivot = self._pivot()
        url = _url(modele, pivot.pk)
        self._compte(url)  # à blanc : régime permanent
        self._semer_lignes_du_pivot(pivot, 10)
        a_10, _reponse = self._compte(url)
        self._semer_lignes_du_pivot(pivot, 15)
        a_25, reponse = self._compte(url)
        return a_10, a_25, reponse

    def test_le_detail_ne_grandit_pas_avec_versions_et_variantes(self):
        a_10, a_25, reponse = self._croissance_du_pivot(DETAIL)
        self.assertEqual(reponse.data['variantes']['total'], 25)
        self.assertEqual(reponse.data['versions']['total'], 25)
        self.assertEqual(
            a_10, a_25,
            'GET %s : %d requêtes à 10 versions/variantes, %d à 25 — N+1.'
            % (DETAIL, a_10, a_25))
        budget, gardee = budget_du_manifeste(DETAIL)
        self.assertTrue(gardee)
        self.assertLessEqual(
            a_25, budget,
            'GET %s : %d requêtes mesurées, plafond %d dans '
            'docs/query-budgets.yml.' % (DETAIL, a_25, budget))

    def test_le_resultat_ne_grandit_pas_avec_versions_et_variantes(self):
        a_10, a_25, _reponse = self._croissance_du_pivot(RESULTAT)
        self.assertEqual(
            a_10, a_25,
            'GET %s : %d requêtes à 10 versions/variantes, %d à 25 — N+1.'
            % (RESULTAT, a_10, a_25))
        budget, gardee = budget_du_manifeste(RESULTAT)
        self.assertTrue(gardee)
        self.assertLessEqual(
            a_25, budget,
            'GET %s : %d requêtes mesurées, plafond %d dans '
            'docs/query-budgets.yml.' % (RESULTAT, a_25, budget))

    def test_detail_et_resultat_tiennent_leur_plafond(self):
        pivot = self._pivot()
        self._semer_lignes_du_pivot(pivot, 10)
        for modele in (DETAIL, RESULTAT):
            with self.subTest(endpoint=modele):
                url = _url(modele, pivot.pk)
                self._compte(url)  # à blanc
                budget, _gardee = budget_du_manifeste(modele)
                with self.assertMaxQueries(budget):
                    reponse = self.api.get(url)
                self.assertEqual(reponse.status_code, 200)
