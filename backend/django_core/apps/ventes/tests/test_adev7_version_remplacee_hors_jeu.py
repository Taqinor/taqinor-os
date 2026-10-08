"""ADEV7 (C-ADEV-002) — une version REMPLACÉE par une révision est hors jeu.

Un prédicat unique ``modifiabilite.geste_cycle_permis`` (ACCEPTER, REFUSER,
ENVOYER, RELANCER) refuse toute version ``is_active=False`` : ``/refuser/``,
``/share-link/ {envoi: true}``, ``/envoyer-email/``, ``/whatsapp/`` et
``/pdf-partage/`` répondent 409 ``{detail, code: "version_remplacee"}`` ; V1
reste ``envoye`` (date_envoi, motif inchangés), aucun ``devis_refused`` /
``devis_sent``. ``mark_devis_sent`` laisse un brouillon archivé brouillon.
Sur la V2 active, les gestes passent comme avant.

Test-du-test : retirer l'appel du prédicat dans ``refuser`` ⇒
``test_refuser_v1_409`` échoue ; retirer ``is_active`` du prédicat ⇒ tous les
tests 409 échouent.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev7_version_remplacee_hors_jeu -v 2
"""
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user,
)


class VersionRemplaceeHorsJeuTests(TestCase):

    def setUp(self):
        self.company = make_company('adev7')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v1 = make_devis(self.company, self.user, self.client_obj,
                             'DEV-ADEV7-0001')
        self.v2 = make_devis(self.company, self.user, self.client_obj,
                             'DEV-ADEV7-0001-V2')
        self.date_envoi = timezone.now()
        Devis.objects.filter(pk=self.v1.pk).update(
            is_active=False, superseded_by=self.v2,
            date_envoi=self.date_envoi)
        Devis.objects.filter(pk=self.v2.pk).update(
            statut=Devis.Statut.BROUILLON, version=2, version_parent=self.v1)
        self.v1.refresh_from_db()
        self.v2.refresh_from_db()
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.evenements = []
        from core.events import devis_refused, devis_sent

        def _ecoute(sender, signal=None, **kwargs):
            self.evenements.append(kwargs.get('devis'))

        for sig, uid in ((devis_refused, 'adev7-r'), (devis_sent, 'adev7-s')):
            sig.connect(_ecoute, dispatch_uid=uid, weak=False)
            self.addCleanup(sig.disconnect, dispatch_uid=uid)

    def _post(self, devis, action, corps=None):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/{action}/', corps or {},
            format='json')

    def _assert_409_v1_intact(self, r):
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['code'], 'version_remplacee')
        self.assertEqual(
            str(r.data['detail']),
            'Cette proposition a été remplacée par DEV-ADEV7-0001-V2.')
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)
        self.assertEqual(self.v1.date_envoi, self.date_envoi)
        self.assertEqual(self.v1.motif_refus, '')
        self.assertEqual(self.evenements, [])

    def test_refuser_v1_409(self):
        self._assert_409_v1_intact(self._post(self.v1, 'refuser'))

    def test_share_link_envoi_v1_409(self):
        self._assert_409_v1_intact(
            self._post(self.v1, 'share-link', {'envoi': True}))

    def test_envoyer_email_v1_409(self):
        with mock.patch('apps.ventes.quote_engine.'
                        'generate_premium_devis_pdf') as rendu:
            r = self._post(self.v1, 'envoyer-email',
                           {'to_email': 'client@example.com'})
        self._assert_409_v1_intact(r)
        rendu.assert_not_called()

    def test_whatsapp_et_pdf_partage_v1_409(self):
        self._assert_409_v1_intact(self._post(self.v1, 'whatsapp'))
        self._assert_409_v1_intact(self._post(self.v1, 'pdf-partage'))

    def test_mark_devis_sent_archive_noop(self):
        from apps.ventes.services import mark_devis_sent
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.BROUILLON, date_envoi=None)
        self.v1.refresh_from_db()
        mark_devis_sent(devis=self.v1, user=self.user)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(self.v1.date_envoi)
        self.assertEqual(self.evenements, [])

    def test_predicat_unique(self):
        from apps.ventes.domain.modifiabilite import (
            GESTES_CYCLE, geste_cycle_permis)
        for geste in GESTES_CYCLE:
            self.assertFalse(geste_cycle_permis(self.v1, geste)[0])
            self.assertEqual(geste_cycle_permis(self.v2, geste), (True, ''))
        with self.assertRaises(ValueError):
            geste_cycle_permis(self.v2, 'INCONNU')

    def test_v2_active_inchangee(self):
        r = self._post(self.v2, 'share-link', {'envoi': True})
        self.assertEqual(r.status_code, 200, r.data)
        self.v2.refresh_from_db()
        self.assertEqual(self.v2.statut, Devis.Statut.ENVOYE)
        r = self._post(self.v2, 'refuser')
        self.assertEqual(r.status_code, 200, r.data)
        self.v2.refresh_from_db()
        self.assertEqual(self.v2.statut, Devis.Statut.REFUSE)
