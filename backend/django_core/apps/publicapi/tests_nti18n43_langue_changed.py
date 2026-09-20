"""NTI18N43 — webhook sortant ``langue_changed`` sur bascule de langue.

CRITÈRE D'ACCEPTATION : un webhook configuré sur ``langue_changed`` reçoit un
payload ``{client_id, ancienne_langue, nouvelle_langue}`` au changement.
L'émission passe par ``core.events.langue_changed`` (bus M6), la livraison par
``delivery.dispatch_event`` — MÊME transport que tous les autres webhooks,
donc la contrainte « dans les 60 secondes » est celle, déjà tenue, de la file
de livraison existante (synchrone à l'émission, puis reprises programmées
NTAPI8). Aucun nouveau mécanisme n'est introduit ici.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from core import events

from . import delivery, i18n_event_receivers
from .constants import ALL_EVENTS, EVENT_CHOICES, EVENT_LANGUE_CHANGED
from .models import Webhook


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class VocabulaireTests(SimpleTestCase):
    """L'évènement fait partie du vocabulaire abonnable, une seule fois."""

    def test_evenement_au_catalogue(self):
        self.assertIn(EVENT_LANGUE_CHANGED, ALL_EVENTS)
        codes = [code for code, _ in EVENT_CHOICES]
        self.assertEqual(codes.count(EVENT_LANGUE_CHANGED), 1)

    def test_le_code_est_celui_nomme_par_le_plan(self):
        self.assertEqual(EVENT_LANGUE_CHANGED, 'langue_changed')


class EmissionTests(SimpleTestCase):
    """``emettre_langue_changed`` n'émet QUE sur un vrai changement."""

    def setUp(self):
        super().setUp()
        self.recus = []
        events.langue_changed.connect(
            self._capter, dispatch_uid='nti18n43-emission')
        self.addCleanup(events.langue_changed.disconnect,
                        self._capter, dispatch_uid='nti18n43-emission')

    def _capter(self, sender, **kwargs):
        self.recus.append(kwargs)

    def test_changement_reel_emet_une_fois(self):
        parti = events.emettre_langue_changed(
            None, ancienne_langue='fr', nouvelle_langue='ar', client_id=7)
        self.assertTrue(parti)
        self.assertEqual(len(self.recus), 1)
        charge = self.recus[0]
        self.assertEqual(charge['client_id'], 7)
        self.assertEqual(charge['ancienne_langue'], 'fr')
        self.assertEqual(charge['nouvelle_langue'], 'ar')
        self.assertEqual(charge['portee'], events.PORTEE_LANGUE_CLIENT)

    def test_valeur_identique_nemet_rien(self):
        for avant, apres in [('fr', 'fr'), ('FR', ' fr '), (None, ''),
                             ('ar', 'AR')]:
            self.assertFalse(events.emettre_langue_changed(
                None, ancienne_langue=avant, nouvelle_langue=apres))
        self.assertEqual(self.recus, [])

    def test_codes_normalises_en_minuscules(self):
        events.emettre_langue_changed(
            None, ancienne_langue=' FR ', nouvelle_langue='AR')
        self.assertEqual(self.recus[0]['ancienne_langue'], 'fr')
        self.assertEqual(self.recus[0]['nouvelle_langue'], 'ar')

    def test_portee_societe_na_pas_de_client(self):
        events.emettre_langue_changed(
            None, ancienne_langue='fr', nouvelle_langue='ar',
            portee=events.PORTEE_LANGUE_SOCIETE)
        self.assertEqual(self.recus[0]['portee'], events.PORTEE_LANGUE_SOCIETE)
        self.assertIsNone(self.recus[0]['client_id'])

    def test_un_abonne_qui_leve_ne_remonte_jamais(self):
        def casse(sender, **kwargs):
            raise RuntimeError('webhook injoignable')

        events.langue_changed.connect(casse, dispatch_uid='nti18n43-casse')
        self.addCleanup(events.langue_changed.disconnect, casse,
                        dispatch_uid='nti18n43-casse')
        with self.assertLogs('core.events', level='WARNING'):
            self.assertTrue(events.emettre_langue_changed(
                None, ancienne_langue='fr', nouvelle_langue='ar'))


class LivraisonWebhookTests(TestCase):
    """Le récepteur ``publicapi`` traduit le signal en webhook sortant."""

    def setUp(self):
        self.co = make_company('pa-i18n43-a', 'PA I18N43 A')

    def test_bascule_client_livre_le_payload_attendu(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            events.emettre_langue_changed(
                self.co, ancienne_langue='fr', nouvelle_langue='ar',
                client_id=123)

        m.assert_called_once()
        args, _kwargs = m.call_args
        self.assertEqual(args[0], self.co.id)
        self.assertEqual(args[1], EVENT_LANGUE_CHANGED)
        payload = args[2]
        # Les trois clés nommées par le plan, telles quelles.
        self.assertEqual(payload['client_id'], 123)
        self.assertEqual(payload['ancienne_langue'], 'fr')
        self.assertEqual(payload['nouvelle_langue'], 'ar')
        self.assertEqual(payload['portee'], events.PORTEE_LANGUE_CLIENT)
        # Aucune donnée personnelle ne s'invite dans la charge utile.
        self.assertEqual(set(payload), {
            'client_id', 'ancienne_langue', 'nouvelle_langue', 'portee'})

    def test_bascule_societe_livre_un_client_nul(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            events.emettre_langue_changed(
                self.co, ancienne_langue='ar', nouvelle_langue='fr',
                portee=events.PORTEE_LANGUE_SOCIETE)

        args, _kwargs = m.call_args
        self.assertIsNone(args[2]['client_id'])
        self.assertEqual(args[2]['portee'], events.PORTEE_LANGUE_SOCIETE)

    def test_sans_societe_rien_nest_livre(self):
        with mock.patch.object(delivery, 'dispatch_event') as m:
            i18n_event_receivers.on_langue_changed(
                sender=None, company=None, ancienne_langue='fr',
                nouvelle_langue='ar', client_id=1)
        m.assert_not_called()

    def test_une_livraison_en_echec_ne_remonte_pas(self):
        with mock.patch.object(delivery, 'dispatch_event',
                               side_effect=RuntimeError('cible morte')):
            with self.assertLogs('apps.publicapi.i18n_event_receivers',
                                 level='ERROR'):
                i18n_event_receivers.on_langue_changed(
                    sender=None, company=self.co, ancienne_langue='fr',
                    nouvelle_langue='ar', client_id=1)

    def test_un_webhook_peut_sabonner_a_levenement(self):
        webhook = Webhook.objects.create(
            company=self.co, target_url='https://exemple.test/hook',
            secret=Webhook.generate_secret(),
            events=[EVENT_LANGUE_CHANGED])
        self.assertTrue(webhook.subscribes_to(EVENT_LANGUE_CHANGED))
