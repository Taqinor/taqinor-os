"""AUD527 — ``figer_periode()`` : une course perdue est un refus PROPRE, plus un 500.

Constat d'audit (le ROUGE figé ici) : ``figer_periode`` lisait
``periode.statut`` SANS ``select_for_update`` avant de créer le
``SnapshotESG`` (OneToOne, contrainte unique en base), et l'action ``figer``
ne capturait que ``DjangoValidationError``. Deux requêtes quasi simultanées
passaient donc TOUTES DEUX le test ``statut != BROUILLON`` avant qu'aucune
n'ait écrit ``FIGEE`` : la seconde levait un ``IntegrityError`` non capturé
→ 500 brut.

La course est reproduite DÉTERMINISTIQUEMENT (sans threads, qui ne verraient
de toute façon pas les écritures non commitées d'une ``TestCase``) par ce
qu'elle est réellement : DEUX instances Python de la même ligne, toutes deux
chargées en ``brouillon``, sur lesquelles on agit l'une après l'autre. Avant
le correctif, la seconde ne relisait jamais la base et fonçait sur la
contrainte unique.

Run :
    python manage.py test apps.esg.tests.test_aud527_figer_concurrent -v2
"""
from datetime import date
from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError

from testkit.base import TenantAPITestCase

from apps.esg.models import PeriodeReportingESG, SnapshotESG
from apps.esg.services import figer_periode


class AUD527FigerPeriodeConcurrentTests(TenantAPITestCase):
    BASE = '/api/django/esg/periodes-esg/'

    def _periode(self):
        return PeriodeReportingESG.objects.create(
            company=self.company, libelle='T1 2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 3, 31))

    def test_seconde_instance_perimee_recoit_un_refus_propre(self):
        """LE ROUGE : la seconde requête tombait sur un IntegrityError."""
        periode = self._periode()
        # Deux « requêtes » ont chargé la ligne, toutes deux en brouillon.
        instance_a = PeriodeReportingESG.objects.get(pk=periode.pk)
        instance_b = PeriodeReportingESG.objects.get(pk=periode.pk)
        self.assertEqual(
            instance_b.statut, PeriodeReportingESG.Statut.BROUILLON)

        figer_periode(instance_a, user=self.user)

        with self.assertRaises(DjangoValidationError):
            figer_periode(instance_b, user=self.user)

        # Un seul snapshot, période figée une seule fois.
        self.assertEqual(
            SnapshotESG.objects.filter(periode=periode).count(), 1)
        periode.refresh_from_db()
        self.assertEqual(periode.statut, PeriodeReportingESG.Statut.FIGEE)

    def test_action_traduit_integrityerror_en_400(self):
        """Seconde barrière : même si la contrainte parlait la première, la
        vue renvoie 400 — jamais un 500 brut."""
        periode = self._periode()
        with patch('apps.esg.services.figer_periode',
                   side_effect=IntegrityError('doublon snapshot')):
            resp = self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('detail', resp.data)

    def test_figeage_normal_inchange(self):
        """Non-régression NTESG1 : le chemin nominal reste identique."""
        periode = self._periode()
        resp = self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        # La réponse sérialisée porte bien le NOUVEAU statut (le verrou ne
        # remplace pas l'instance de l'appelant).
        self.assertEqual(resp.data['statut'], PeriodeReportingESG.Statut.FIGEE)
        periode.refresh_from_db()
        self.assertEqual(periode.statut, PeriodeReportingESG.Statut.FIGEE)
        self.assertEqual(
            SnapshotESG.objects.filter(periode=periode).count(), 1)
