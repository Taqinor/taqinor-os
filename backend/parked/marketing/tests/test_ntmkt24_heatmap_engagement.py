"""NTMKT24 — Heatmap d'engagement hebdomadaire par heure d'envoi.

Sélecteur LECTURE SEULE : agrège les taux d'ouverture historiques
(``EnvoiCampagne``, XMKT2) par jour de semaine × heure. Purement informatif —
il ne bloque jamais un envoi.
"""
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company

from apps.marketing import selectors as mkt_selectors
from apps.marketing.models import Campagne, EnvoiCampagne


class HeatmapEngagementTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt24', nom='NTMKT24')
        self.campagne = Campagne.objects.create(company=self.co, nom='C')

    def _envoi(self, envoye_le, ouvert=False):
        return EnvoiCampagne.objects.create(
            company=self.co, campagne=self.campagne,
            destinataire='a@b.ma', envoye_le=envoye_le,
            ouvert_le=envoye_le if ouvert else None)

    def _local(self, *args):
        return timezone.make_aware(
            datetime.datetime(*args), timezone.get_current_timezone())

    def test_societe_sans_historique_renvoie_un_etat_vide(self):
        data = mkt_selectors.heatmap_engagement(self.co)
        self.assertEqual(data, {'cellules': [], 'meilleur': None,
                                'total_envois': 0})

    def test_agregation_par_jour_et_heure(self):
        mardi_10h = self._local(2026, 7, 7, 10, 0)   # mardi
        lundi_9h = self._local(2026, 7, 6, 9, 0)     # lundi
        self._envoi(mardi_10h, ouvert=True)
        self._envoi(mardi_10h, ouvert=True)
        self._envoi(mardi_10h, ouvert=False)
        self._envoi(lundi_9h, ouvert=False)
        maintenant = self._local(2026, 7, 20, 12, 0)
        data = mkt_selectors.heatmap_engagement(self.co, maintenant=maintenant)
        self.assertEqual(data['total_envois'], 4)
        cases = {(c['jour'], c['heure']): c for c in data['cellules']}
        self.assertAlmostEqual(cases[(1, 10)]['taux_ouverture'], 0.6667, 3)
        self.assertEqual(cases[(1, 10)]['envois'], 3)
        self.assertEqual(cases[(0, 9)]['taux_ouverture'], 0.0)
        self.assertEqual((data['meilleur']['jour'], data['meilleur']['heure']),
                         (1, 10))

    def test_les_envois_hors_fenetre_sont_ignores(self):
        vieux = timezone.now() - datetime.timedelta(days=400)
        self._envoi(vieux, ouvert=True)
        data = mkt_selectors.heatmap_engagement(self.co, jours=180)
        self.assertEqual(data['total_envois'], 0)

    def test_les_envois_non_partis_sont_ignores(self):
        EnvoiCampagne.objects.create(
            company=self.co, campagne=self.campagne,
            destinataire='queued@b.ma', envoye_le=None)
        self.assertEqual(
            mkt_selectors.heatmap_engagement(self.co)['total_envois'], 0)

    def test_scoping_societe(self):
        autre = Company.objects.create(slug='ntmkt24b', nom='Autre')
        campagne_b = Campagne.objects.create(company=autre, nom='B')
        EnvoiCampagne.objects.create(
            company=autre, campagne=campagne_b, destinataire='x@b.ma',
            envoye_le=timezone.now(), ouvert_le=timezone.now())
        self.assertEqual(
            mkt_selectors.heatmap_engagement(self.co)['total_envois'], 0)
        self.assertEqual(
            mkt_selectors.heatmap_engagement(autre)['total_envois'], 1)

    def test_endpoint_exige_une_authentification(self):
        res = self.client.get(reverse('mkt-heatmap-engagement'))
        self.assertIn(res.status_code, (401, 403))
