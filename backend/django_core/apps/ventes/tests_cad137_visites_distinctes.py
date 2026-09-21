"""CAD137 — « rouvert 3 fois » ne se déclenche plus sur une seule visite.

Audit L3 du 21/09/2026, section CAD-K. Le compteur de consultations était
incrémenté par TROIS portes — la page de proposition, le PDF public et le
document tokenisé — à chaque GET, et l'alerte « rouverte 3 fois, le client
hésite, appelez » se déclenchait sur ``view_count >= 3`` : lire sa page, puis
télécharger le PDF, puis recharger suffisait. La protection
anti-rechargement de 15 minutes ne couvrait QUE la notification. L'alerte la
plus forte du système partait donc sur le comportement le plus banal.

Ce fichier verrouille :

  * trois chargements en cinq minutes ne comptent que pour UNE visite (et ne
    déclenchent donc pas l'alerte) ;
  * trois visites distinctes la déclenchent ;
  * ``last_viewed_at`` reste écrit à CHAQUE GET — c'est la vérité de « vu
    pour la dernière fois », et rien ne s'en sert pour compter ;
  * le seuil est NOMMÉ et dit la même chose que le libellé de l'alerte.

Le temps est GELÉ : la fenêtre de sessionisation est exactement la question
qu'une horloge vivante rend instable.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from testkit.time import frozen

from apps.crm.models import Client
from apps.ventes import public_views, scheduled
from apps.ventes.models import Devis, ShareLink

#: Mardi 15 septembre 2026, 10 h UTC.
MAINTENANT = datetime.datetime(
    2026, 9, 15, 10, 0, tzinfo=datetime.timezone.utc)


class CompteurDeVisitesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD137', slug='cad137')
        self.client_final = Client.objects.create(
            company=self.company, nom='Benali')
        self.devis = Devis.objects.create(
            company=self.company, reference='DV-CAD137',
            client=self.client_final)

    def _lien(self):
        return ShareLink.objects.create(
            company=self.company, devis=self.devis, token='cad137-token',
            expires_at=timezone.now() + datetime.timedelta(days=30))

    def _vue(self, lien, instant):
        """Un GET public du lien, à l'instant donné."""
        with frozen(instant):
            lien.refresh_from_db()
            public_views._stamp_view(lien)
        lien.refresh_from_db()
        return lien

    def test_trois_chargements_en_cinq_minutes_valent_une_visite(self):
        """LE cas de l'audit : page, PDF, rechargement."""
        lien = self._lien()
        self._vue(lien, MAINTENANT)
        self._vue(lien, MAINTENANT + datetime.timedelta(minutes=2))
        self._vue(lien, MAINTENANT + datetime.timedelta(minutes=5))
        self.assertEqual(lien.view_count, 1)

    def test_trois_visites_distinctes_comptent_trois(self):
        lien = self._lien()
        self._vue(lien, MAINTENANT)
        self._vue(lien, MAINTENANT + datetime.timedelta(minutes=30))
        self._vue(lien, MAINTENANT + datetime.timedelta(hours=5))
        self.assertEqual(lien.view_count, 3)

    def test_la_fenetre_est_celle_qui_protege_deja_la_notification(self):
        """Une seule source, un seul délai (QJ1bis).

        La fenêtre court depuis la DERNIÈRE vue, pas depuis la première —
        exactement comme la notification, qui compare ``now`` au
        ``last_viewed_at`` précédent. C'est ce qui fait qu'une lecture
        continue (page, PDF, rechargement, retour) reste UNE visite quelle
        que soit sa durée : le troisième chargement ci-dessous repart donc de
        ``juste_avant``, pas de ``MAINTENANT``.
        """
        lien = self._lien()
        self._vue(lien, MAINTENANT)
        juste_avant = MAINTENANT + public_views.REOUVERTURE_FENETRE \
            - datetime.timedelta(seconds=1)
        self._vue(lien, juste_avant)
        self.assertEqual(lien.view_count, 1)
        self._vue(lien, juste_avant + public_views.REOUVERTURE_FENETRE)
        self.assertEqual(lien.view_count, 2)

    def test_la_derniere_vue_est_ecrite_a_chaque_get(self):
        """`last_viewed_at` dit la vérité, il ne sert pas à compter."""
        lien = self._lien()
        self._vue(lien, MAINTENANT)
        rechargement = MAINTENANT + datetime.timedelta(minutes=3)
        self._vue(lien, rechargement)
        self.assertEqual(lien.last_viewed_at, rechargement)
        self.assertEqual(lien.view_count, 1)

    def test_la_premiere_vue_est_horodatee_une_seule_fois(self):
        lien = self._lien()
        self._vue(lien, MAINTENANT)
        premiere = lien.first_viewed_at
        self._vue(lien, MAINTENANT + datetime.timedelta(hours=2))
        self.assertEqual(lien.first_viewed_at, premiere)


class SeuilAlerteTests(TestCase):
    def test_le_seuil_est_nomme_et_vaut_trois(self):
        """Le seuil et le libellé « rouverte 3 fois » disent la même chose."""
        self.assertEqual(scheduled._REOUVERTURES_ALERTE, 3)
