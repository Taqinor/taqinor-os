"""NTDATA41 — alertes de TENDANCE et d'ANOMALIE sur une métrique nommée.

Couvre :
  * le critère d'acceptation : une chute de MRR > 20 % vs le mois précédent
    déclenche une alerte `variation` ;
  * une hausse ne la déclenche PAS (l'opérateur décide du sens) ;
  * le mode `anomalie` compare le z-score du dernier point à son seuil ;
  * la PÉRIODE COURANTE est exclue — sinon toute alerte partirait le 1er du
    mois sur un mois de trois jours ;
  * une dérivée NON CALCULABLE (moins de 2 périodes, période précédente à 0)
    ne déclenche RIEN — jamais un 0 qui ferait passer une absence de mesure
    pour une stabilité ;
  * le mode `seuil` (défaut) est inchangé pour toutes les alertes existantes ;
  * variation/anomalie sont REFUSÉES sur une source `catalogue` (pas
    d'historique), au CHAMP fautif ;
  * la notification NOMME la métrique et ce qui a été comparé.

L'horloge est FIGÉE : « période courante » dépend du mois réel.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.reporting import kpi_alertes
from apps.reporting.models import KpiAlerte
from apps.semantic import selectors as semantic_selectors
from apps.semantic.models import MetricDefinition
from authentication.models import Company
from testkit.time import frozen

User = get_user_model()

#: Mi-avril 2026 : mars et février sont COMPLETS, avril est en cours.
AVRIL_2026 = '2026-04-15 09:00:00'


class VariationAnomalieTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA41 SA',
                                             slug='ntdata41-sa')
        cls.user = User.objects.create_user(
            username='ntdata41_u', password='x', company=cls.company,
            role_legacy='admin')
        cls.metrique = MetricDefinition.objects.create(
            company=cls.company, cle='mrr', libelle='MRR',
            dataset='ventes_factures',
            mesure={'field': 'montant_ttc', 'agg': 'sum'},
            unite=MetricDefinition.Unite.MAD)

    def _alerte(self, **kw):
        params = dict(company=self.company, nom='Chute MRR',
                      source=KpiAlerte.Source.METRIQUE,
                      metric_definition=self.metrique,
                      mode_detection=KpiAlerte.ModeDetection.VARIATION,
                      operateur=KpiAlerte.Operateur.INF,
                      seuil=Decimal('-20'))
        params.update(kw)
        return KpiAlerte.objects.create(**params)

    def _serie(self, valeurs):
        """Double de série mensuelle : ``[(annee, mois, valeur), …]``."""
        return [{'periode': '%04d-%02d' % (a, m), 'valeur': v}
                for a, m, v in valeurs]

    # ── Critère d'acceptation ──────────────────────────────────────────────
    def test_chute_de_mrr_superieure_a_20_pct_declenche(self):
        alerte = self._alerte()
        serie = self._serie([(2026, 2, 10000), (2026, 3, 7000),
                             (2026, 4, 300)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            valeur, franchi, notifie = kpi_alertes.evaluate_kpi_alerte(alerte)
        # 7000 vs 10000 = -30 % : au-delà des -20 % tolérés.
        self.assertEqual(valeur, Decimal('-30.00'))
        self.assertTrue(franchi)
        self.assertTrue(notifie)

    def test_hausse_ne_declenche_pas_une_alerte_de_chute(self):
        alerte = self._alerte()
        serie = self._serie([(2026, 2, 7000), (2026, 3, 10000),
                             (2026, 4, 300)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            valeur, franchi, _notifie = kpi_alertes.evaluate_kpi_alerte(alerte)
        self.assertGreater(valeur, 0)
        self.assertFalse(franchi)

    def test_petite_baisse_sous_le_seuil_ne_declenche_pas(self):
        alerte = self._alerte()
        serie = self._serie([(2026, 2, 10000), (2026, 3, 9000),
                             (2026, 4, 300)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            valeur, franchi, _n = kpi_alertes.evaluate_kpi_alerte(alerte)
        self.assertEqual(valeur, Decimal('-10.00'))
        self.assertFalse(franchi)

    def test_periode_courante_exclue(self):
        """Avril (en cours, 300) ne doit JAMAIS entrer dans la comparaison."""
        serie = self._serie([(2026, 2, 10000), (2026, 3, 9000),
                             (2026, 4, 300)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            pourcentage, courante, precedente = (
                semantic_selectors.variation_pct(self.company, self.user,
                                                 'mrr'))
        self.assertEqual(courante, 9000.0)
        self.assertEqual(precedente, 10000.0)
        self.assertAlmostEqual(pourcentage, -10.0)

    # ── Dérivées non calculables ───────────────────────────────────────────
    def test_moins_de_deux_periodes_completes_ne_declenche_rien(self):
        alerte = self._alerte()
        serie = self._serie([(2026, 3, 7000), (2026, 4, 300)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            valeur, franchi, _n = kpi_alertes.evaluate_kpi_alerte(alerte)
        self.assertIsNone(valeur)
        self.assertFalse(franchi)

    def test_periode_precedente_a_zero_ne_declenche_rien(self):
        """« +∞ % » n'est pas un nombre à comparer à un seuil."""
        alerte = self._alerte()
        serie = self._serie([(2026, 2, 0), (2026, 3, 7000), (2026, 4, 300)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            valeur, franchi, _n = kpi_alertes.evaluate_kpi_alerte(alerte)
        self.assertIsNone(valeur)
        self.assertFalse(franchi)

    # ── Mode anomalie ──────────────────────────────────────────────────────
    def test_anomalie_flague_un_dernier_point_aberrant(self):
        alerte = self._alerte(
            mode_detection=KpiAlerte.ModeDetection.ANOMALIE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('2'))
        # 8 périodes COMPLÈTES, la dernière (mars) très au-dessus : |z| ≈ 2,65
        # (le maximum atteignable sur 8 points est √7 ≈ 2,65 — au-delà de
        # 2 écarts-types, donc franchi).
        serie = self._serie([(2025, 8, 100), (2025, 9, 102), (2025, 10, 98),
                             (2025, 11, 101), (2025, 12, 99), (2026, 1, 100),
                             (2026, 2, 103), (2026, 3, 900), (2026, 4, 50)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            valeur, franchi, _n = kpi_alertes.evaluate_kpi_alerte(alerte)
        self.assertIsNotNone(valeur)
        self.assertGreater(valeur, Decimal('2'))
        self.assertTrue(franchi)

    def test_anomalie_serie_plate_ne_declenche_rien(self):
        alerte = self._alerte(
            mode_detection=KpiAlerte.ModeDetection.ANOMALIE,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('2'))
        serie = self._serie([(2025, 12, 100), (2026, 1, 100),
                             (2026, 2, 100), (2026, 3, 100)])
        with frozen(AVRIL_2026), _serie_figee(serie):
            valeur, franchi, _n = kpi_alertes.evaluate_kpi_alerte(alerte)
        self.assertIsNone(valeur)
        self.assertFalse(franchi)

    # ── Rétro-compatibilité & garde-fous ───────────────────────────────────
    def test_mode_seuil_par_defaut(self):
        alerte = self._alerte(mode_detection=KpiAlerte.ModeDetection.SEUIL)
        self.assertEqual(
            KpiAlerte.objects.get(pk=alerte.pk).mode_detection, 'seuil')
        neuve = KpiAlerte(company=self.company, kpi=KpiAlerte.Kpi.DSO,
                          seuil=Decimal('60'))
        self.assertEqual(neuve.mode_detection, KpiAlerte.ModeDetection.SEUIL)
        neuve.clean()  # ne lève pas

    def test_variation_sur_catalogue_refusee_au_champ_fautif(self):
        alerte = KpiAlerte(
            company=self.company, source=KpiAlerte.Source.CATALOGUE,
            kpi=KpiAlerte.Kpi.DSO, seuil=Decimal('-20'),
            mode_detection=KpiAlerte.ModeDetection.VARIATION)
        with self.assertRaises(ValidationError) as leve:
            alerte.clean()
        self.assertIn('mode_detection', leve.exception.message_dict)

    def test_notification_nomme_la_metrique_et_la_comparaison(self):
        alerte = self._alerte()
        envoyes = []
        import apps.notifications.services as notif_services
        reel = notif_services.notify

        def _capture(user, event, title, body='', company=None, **kw):
            envoyes.append((title, body))
            return reel(user, event, title, body=body, company=company, **kw)

        serie = self._serie([(2026, 2, 10000), (2026, 3, 7000)])
        alerte.destinataires_utilisateurs.add(self.user)
        with frozen(AVRIL_2026), _serie_figee(serie), \
                _patch(notif_services, 'notify', _capture):
            kpi_alertes.evaluate_kpi_alerte(alerte)
        self.assertTrue(envoyes)
        titre, corps = envoyes[0]
        self.assertIn('MRR', titre)
        self.assertIn('variation', corps.lower())


# ── Doubles de test ────────────────────────────────────────────────────────

def _serie_figee(points):
    """Fige la série mensuelle rendue par la couche sémantique.

    On double la SÉRIE, pas le résolveur : le calcul de variation et le
    scoring d'anomalie sont exactement le code de production, et le test reste
    déterministe sans monter un jeu de factures par mois.
    """
    from unittest import mock
    return mock.patch.object(
        semantic_selectors, 'serie_temporelle',
        lambda company, user, cle, **kw: list(points))


def _patch(module, nom, valeur):
    from unittest import mock
    return mock.patch.object(module, nom, valeur)
