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
        # api-fuzz 01/11 : ce 409 n'a pas de ``statut`` -> le schéma publié du
        # 409 ne l'exige plus (seul ``detail`` est commun aux deux refus).
        from apps.ventes.views import openapi_docs
        champs = openapi_docs.EnvoyerEmailSansDestinataire.fields
        self.assertFalse(champs['statut'].required)
        self.assertTrue(champs['detail'].required)
        self.assertEqual(r.data['successeur']['reference'],
                         'DEV-ADEV7-0001-V2')

    def test_whatsapp_et_pdf_partage_v1_409(self):
        self._assert_409_v1_intact(self._post(self.v1, 'whatsapp'))
        self._assert_409_v1_intact(self._post(self.v1, 'pdf-partage'))

    def test_whatsapp_lead_v1_et_envoi_refuse_expire_409(self):
        """AMSG85 (origine AMSG38) — ``whatsapp-preview/`` sur V1, un refusé
        et un expiré ; les deux routes WhatsApp de la fiche lead sur V1 ;
        ``whatsapp/``, ``envoyer-email/`` et ``share-link {envoi}`` sur le
        refusé et l'expiré : 409 ``version_remplacee`` sans ``wa_url``, aucun
        effet. Mutants : retirer l'appel dans ``whatsapp_preview`` ⇒ échec ;
        retirer la boucle ``geste_cycle_permis`` de la vue lead ⇒ échec."""
        from apps.audit.models import AuditLog
        from apps.crm.models import Lead, LeadActivity
        from apps.ventes.domain.modifiabilite import MESSAGE_HORS_JEU
        from apps.ventes.models import ShareLink
        lead = Lead.objects.create(
            company=self.company, nom='Lead AMSG85', telephone='+212612340041')
        Devis.objects.filter(pk__in=[self.v1.pk, self.v2.pk]).update(lead=lead)
        hors_jeu = {}
        for statut, ref in ((Devis.Statut.REFUSE, 'DEV-AMSG85-REF'),
                            (Devis.Statut.EXPIRE, 'DEV-AMSG85-EXP')):
            d = make_devis(self.company, self.user, self.client_obj, ref)
            Devis.objects.filter(pk=d.pk).update(statut=statut, date_envoi=self.date_envoi)
            hors_jeu[statut] = d
        liens_avant = ShareLink.objects.count()

        def _refus(r, message):
            self.assertEqual(r.status_code, 409, r.data)
            self.assertEqual(r.data['code'], 'version_remplacee')
            self.assertEqual(str(r.data['detail']), message)
            self.assertNotIn('wa_url', r.data)

        r = self._post(self.v1, 'whatsapp-preview')
        _refus(r, 'Cette proposition a été remplacée par DEV-ADEV7-0001-V2.')
        self.assertEqual(r.data['successeur']['id'], self.v2.pk)
        for route in ('whatsapp-devis-apercu', 'whatsapp-devis'):
            with self.subTest(route=route):
                _refus(self.api.post(f'/api/django/crm/leads/{lead.pk}/{route}/',
                                     {'devis_ids': [self.v1.pk]}, format='json'),
                       'Cette proposition a été remplacée par DEV-ADEV7-0001-V2.')
        with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf') as rendu:
            for d in hors_jeu.values():
                for action, corps in (('whatsapp-preview', None), ('whatsapp', None),
                                      ('envoyer-email', {'to_email': 'client@example.com'}),
                                      ('share-link', {'envoi': True})):
                    with self.subTest(statut=d.reference, action=action):
                        _refus(self._post(d, action, corps), MESSAGE_HORS_JEU)
        rendu.assert_not_called()
        # CLAUSE PERSISTANCE — relus : statuts et date d'envoi inchangés.
        self.v1.refresh_from_db()
        self.assertEqual((self.v1.statut, self.v1.date_envoi), (Devis.Statut.ENVOYE, self.date_envoi))
        for statut, d in hors_jeu.items():
            d.refresh_from_db()
            self.assertEqual((d.statut, d.date_envoi), (statut, self.date_envoi))
        self.assertEqual(ShareLink.objects.count(), liens_avant)
        self.assertEqual(self.evenements, [])
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.WHATSAPP).exists())
        self.assertFalse(LeadActivity.objects.filter(lead=lead, kind=LeadActivity.Kind.NOTE).exists())

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
