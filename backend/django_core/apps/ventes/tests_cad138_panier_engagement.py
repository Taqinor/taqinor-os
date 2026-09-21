"""CAD138 — le panier « relance d'engagement » se vide, et l'expiration passe devant.

Audit L3 du 21/09/2026, section CAD-K. Un déclencheur allumé était inscrit
UNE FOIS POUR TOUTES — deux sites d'écriture, tous deux additifs, aucun code
de remise à zéro — et le panier engagement passait AVANT le test
d'expiration : un devis dont la validité tombait dans trois jours restait
caché derrière un drapeau « non ouvert » vieux de trois semaines.

Ce fichier verrouille les deux corrections, et rien d'autre :

  * un déclencheur de plus de ``DECLENCHEUR_PEREMPTION_JOURS`` jours SORT du
    panier ; un déclencheur récent y reste ;
  * un devis qui EXPIRE passe devant l'engagement ;
  * la forme historique (liste sans date) continue d'être lue, datée par la
    meilleure preuve disponible — aucune migration, aucun signal jeté faute
    de savoir le dater.
"""
import datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes import selectors
from apps.ventes.models import Devis, ShareLink


class FormeDesDeclencheursTests(SimpleTestCase):
    """Lecture/écriture de la forme, sans base."""

    def test_la_liste_historique_est_lue_sans_date(self):
        lien = ShareLink(engagement_triggers_fired=['reopened_3x'])
        self.assertEqual(selectors.dates_declencheurs(lien),
                         {'reopened_3x': None})

    def test_un_champ_vide_ne_casse_rien(self):
        self.assertEqual(
            selectors.dates_declencheurs(ShareLink()), {})

    def test_marquer_ecrit_une_date(self):
        lien = ShareLink(engagement_triggers_fired=['reopened_3x'])
        quand = timezone.now()
        selectors.marquer_declencheur(lien, 'not_opened_24h', quand=quand)
        dates = selectors.dates_declencheurs(lien)
        self.assertEqual(set(dates), {'reopened_3x', 'not_opened_24h'})
        self.assertEqual(dates['not_opened_24h'], quand.isoformat())
        # La clé historique est CONSERVÉE, sans date inventée.
        self.assertIsNone(dates['reopened_3x'])

    def test_rallumer_rafraichit_la_date(self):
        lien = ShareLink()
        vieux = timezone.now() - datetime.timedelta(days=30)
        selectors.marquer_declencheur(lien, 'reopened_3x', quand=vieux)
        neuf = timezone.now()
        selectors.marquer_declencheur(lien, 'reopened_3x', quand=neuf)
        self.assertEqual(
            selectors.dates_declencheurs(lien)['reopened_3x'],
            neuf.isoformat())

    def test_un_declencheur_recent_reste_actif(self):
        lien = ShareLink()
        selectors.marquer_declencheur(lien, 'reopened_3x')
        self.assertEqual(selectors.declencheurs_actifs(lien),
                         {'reopened_3x'})

    def test_un_declencheur_perime_sort_du_panier(self):
        lien = ShareLink()
        vieux = timezone.now() - datetime.timedelta(
            days=selectors.DECLENCHEUR_PEREMPTION_JOURS + 1)
        selectors.marquer_declencheur(lien, 'reopened_3x', quand=vieux)
        self.assertEqual(selectors.declencheurs_actifs(lien), set())

    def test_une_date_illisible_ne_jette_pas_le_signal(self):
        lien = ShareLink(engagement_triggers_fired={'reopened_3x': 'hier'})
        self.assertEqual(selectors.declencheurs_actifs(lien),
                         {'reopened_3x'})


class PanierTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAD138', slug='cad138')
        self.client_final = Client.objects.create(
            company=self.company, nom='Benali')
        self.today = timezone.localdate()
        self.now = timezone.now()

    def _devis(self, reference, **extra):
        devis = Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_final, statut=Devis.Statut.ENVOYE, **extra)
        Devis.objects.filter(pk=devis.pk).update(
            date_envoi=self.now - datetime.timedelta(days=30))
        devis.refresh_from_db()
        return devis

    def _lien(self, devis, *, token, declencheur=None, quand=None):
        lien = ShareLink.objects.create(
            company=self.company, devis=devis, token=token,
            expires_at=self.now + datetime.timedelta(days=30))
        if declencheur:
            selectors.marquer_declencheur(lien, declencheur, quand=quand)
            lien.save(update_fields=['engagement_triggers_fired'])
        return lien

    def _paniers(self):
        return selectors.devis_action_requise(self.company)['buckets']

    def test_un_declencheur_de_plus_de_n_jours_sort_du_panier(self):
        devis = self._devis('DV-138-A')
        self._lien(devis, token='cad138-a', declencheur='not_opened_24h',
                   quand=self.now - datetime.timedelta(
                       days=selectors.DECLENCHEUR_PEREMPTION_JOURS + 1))
        paniers = self._paniers()
        self.assertNotIn(devis.id, paniers['engagement_relance']['ids'])

    def test_un_declencheur_recent_reste_dans_le_panier(self):
        devis = self._devis('DV-138-B')
        self._lien(devis, token='cad138-b', declencheur='reopened_3x',
                   quand=self.now - datetime.timedelta(days=1))
        paniers = self._paniers()
        self.assertIn(devis.id, paniers['engagement_relance']['ids'])

    def test_un_devis_qui_expire_passe_devant_lengagement(self):
        """LE cas de l'audit : la validité tombe, le drapeau est vieux."""
        devis = self._devis(
            'DV-138-C',
            date_validite=self.today + datetime.timedelta(days=3))
        self._lien(devis, token='cad138-c', declencheur='reopened_3x',
                   quand=self.now - datetime.timedelta(days=1))
        paniers = self._paniers()
        self.assertIn(devis.id, paniers['expirant_bientot']['ids'])
        self.assertNotIn(devis.id, paniers['engagement_relance']['ids'])

    def test_un_devis_tombe_toujours_dans_un_seul_panier(self):
        devis = self._devis(
            'DV-138-D',
            date_validite=self.today + datetime.timedelta(days=2))
        self._lien(devis, token='cad138-d', declencheur='reopened_3x')
        paniers = self._paniers()
        presences = [cle for cle, bloc in paniers.items()
                     if devis.id in bloc['ids']]
        self.assertEqual(presences, ['expirant_bientot'], presences)
