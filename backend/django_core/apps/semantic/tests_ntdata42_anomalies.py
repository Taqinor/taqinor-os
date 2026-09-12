"""NTDATA42 — détection d'anomalie sur les séries de métriques (job Beat).

Couvre :
  * le critère d'acceptation : une valeur ABERRANTE crée un `AnomalyFlag` lié
    à la métrique ET à la période ;
  * une série RÉGULIÈRE ne crée rien (aucun faux positif) ;
  * une série trop COURTE ne crée rien — la borne |z| ≤ (n-1)/√n rend le
    signalement arithmétiquement impossible avant ~9 périodes ;
  * la période COURANTE est exclue de la série ;
  * deux périodes aberrantes de la même métrique = DEUX faits distincts ;
  * rejouer le job ne duplique pas un signalement déjà ouvert ;
  * une métrique INACTIVE est ignorée ;
  * le scoping société.

L'horloge est FIGÉE : « période courante » dépend du mois réel.
"""
from unittest import mock

from django.test import TestCase

from apps.semantic import selectors as semantic_selectors
from apps.semantic import tasks as semantic_tasks
from apps.semantic.models import MetricDefinition
from authentication.models import Company
from core.models import AnomalyFlag
from testkit.time import frozen

AVRIL_2026 = '2026-04-15 09:00:00'

#: 8 mois réguliers + un mois très au-dessus = 9 périodes complètes ; |z| du
#: point aberrant ≈ 2,67, au-delà du seuil de 2,5.
SERIE_ABERRANTE = [
    (2025, 7, 100), (2025, 8, 102), (2025, 9, 98), (2025, 10, 101),
    (2025, 11, 99), (2025, 12, 100), (2026, 1, 103), (2026, 2, 97),
    (2026, 3, 900),
    # Avril est la période EN COURS : elle ne doit jamais entrer dans le calcul.
    (2026, 4, 12),
]

SERIE_REGULIERE = [
    (2025, 7, 100), (2025, 8, 102), (2025, 9, 98), (2025, 10, 101),
    (2025, 11, 99), (2025, 12, 100), (2026, 1, 103), (2026, 2, 97),
    (2026, 3, 101),
]


def _points(valeurs):
    return [{'periode': '%04d-%02d' % (a, m), 'valeur': v}
            for a, m, v in valeurs]


def _serie_figee(valeurs):
    return mock.patch.object(
        semantic_selectors, 'serie_temporelle',
        lambda company, user, cle, **kw: _points(valeurs))


class DetecterAnomaliesMetriquesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA42 SA',
                                             slug='ntdata42-sa')
        cls.autre = Company.objects.create(nom='NTDATA42 Autre',
                                           slug='ntdata42-autre')
        cls.metrique = MetricDefinition.objects.create(
            company=cls.company, cle='ca_ht', libelle='CA HT',
            dataset='ventes_factures',
            mesure={'field': 'montant_ht', 'agg': 'sum'},
            unite=MetricDefinition.Unite.MAD)

    def _lancer(self, valeurs):
        with frozen(AVRIL_2026), _serie_figee(valeurs):
            return semantic_tasks.detecter_anomalies_metriques(
                company=self.company)

    def test_valeur_aberrante_cree_un_flag_lie_metrique_et_periode(self):
        """Critère d'acceptation NTDATA42."""
        recap = self._lancer(SERIE_ABERRANTE)
        self.assertEqual(recap[0]['nb_anomalies'], 1)

        flag = AnomalyFlag.objects.get(company=self.company)
        self.assertEqual(flag.subject_type, semantic_tasks.SUBJECT_TYPE)
        # L'identité du signalement porte LA MÉTRIQUE ET LA PÉRIODE.
        self.assertEqual(flag.subject_id,
                         '%s:2026-03' % self.metrique.pk)
        self.assertEqual(flag.metric, 'ca_ht')
        self.assertIn('CA HT', flag.message)
        self.assertIn('2026-03', flag.message)
        self.assertEqual(flag.value, 900.0)
        self.assertGreater(abs(flag.score), semantic_tasks.SEUIL_Z)
        self.assertEqual(flag.status, AnomalyFlag.STATUS_OUVERT)

    def test_periode_courante_exclue_de_la_serie(self):
        """Avril (12) est en cours : il ne peut pas être signalé."""
        self._lancer(SERIE_ABERRANTE)
        self.assertFalse(
            AnomalyFlag.objects.filter(subject_id__endswith='2026-04')
            .exists())

    def test_serie_reguliere_ne_cree_rien(self):
        recap = self._lancer(SERIE_REGULIERE)
        self.assertEqual(recap[0]['nb_anomalies'], 0)
        self.assertEqual(AnomalyFlag.objects.count(), 0)

    def test_serie_trop_courte_ne_cree_rien(self):
        """Sous MIN_POINTS, « l'habitude » n'est pas une notion."""
        courte = [(2026, 1, 100), (2026, 2, 100), (2026, 3, 900)]
        recap = self._lancer(courte)
        self.assertEqual(recap[0]['nb_anomalies'], 0)
        self.assertEqual(AnomalyFlag.objects.count(), 0)

    def test_deux_periodes_aberrantes_sont_deux_faits(self):
        """L'identité d'un signalement = LA MÉTRIQUE ET LA PÉRIODE.

        Deux mois aberrants de la même métrique sont deux faits distincts : le
        second ne doit pas être avalé par la dédup du premier. On les fait
        apparaître à deux passages (deux pics simultanés se masquent l'un
        l'autre en gonflant l'écart-type — le scorer ne les verrait ni l'un ni
        l'autre, ce qui est son garde-fou, pas un bug).
        """
        janvier_aberrant = [(2025, 7, 100), (2025, 8, 102), (2025, 9, 98),
                            (2025, 10, 101), (2025, 11, 99), (2025, 12, 100),
                            (2026, 1, 900), (2026, 2, 97), (2026, 3, 101)]
        self._lancer(janvier_aberrant)
        self._lancer(SERIE_ABERRANTE)
        sujets = set(AnomalyFlag.objects.values_list('subject_id', flat=True))
        self.assertEqual(
            sujets,
            {'%s:2026-01' % self.metrique.pk,
             '%s:2026-03' % self.metrique.pk})

    def test_rejouer_ne_duplique_pas(self):
        self._lancer(SERIE_ABERRANTE)
        self._lancer(SERIE_ABERRANTE)
        self.assertEqual(AnomalyFlag.objects.count(), 1)

    def test_metrique_inactive_ignoree(self):
        MetricDefinition.objects.filter(pk=self.metrique.pk).update(
            actif=False)
        recap = self._lancer(SERIE_ABERRANTE)
        self.assertEqual(recap[0]['nb_anomalies'], 0)
        self.assertEqual(AnomalyFlag.objects.count(), 0)

    def test_scoping_societe(self):
        self._lancer(SERIE_ABERRANTE)
        self.assertEqual(
            AnomalyFlag.objects.filter(company=self.autre).count(), 0)
        self.assertEqual(
            AnomalyFlag.objects.filter(company=self.company).count(), 1)

    def test_fan_out_sur_les_societes_actives(self):
        with frozen(AVRIL_2026), _serie_figee(SERIE_REGULIERE):
            recap = semantic_tasks.detecter_anomalies_metriques()
        societes = {ligne['company'] for ligne in recap}
        self.assertIn(self.company.pk, societes)
        self.assertIn(self.autre.pk, societes)
