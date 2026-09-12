"""NTAPI17 — flux d'évènements consommable (CDC léger) `GET /events/`.

Critère d'acceptation : consommer depuis `after=0` puis re-poller avec le
dernier `sequence` ne renvoie QUE les évènements neufs, DANS L'ORDRE.

Vérifie en plus les trois propriétés qui font qu'un flux CDC est utilisable :
la séquence est par SOCIÉTÉ (jamais la PK globale, qui divulguerait le volume
des autres tenants), le flux est alimenté par les mêmes signaux que les
webhooks même quand PERSONNE n'est abonné, et il n'est jamais un contournement
des scopes de lecture.
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from . import delivery, events_feed
from .constants import (
    EVENT_FACTURE_PAID, EVENT_LEAD_CREATED, EVENT_TICKET_CREATED,
    SCOPE_READ_EVENTS, SCOPE_READ_FACTURES, SCOPE_READ_LEADS,
)
from .models import ApiEvent, ApiKey


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi17SequenceTests(TestCase):
    """La séquence : dense, croissante, PAR SOCIÉTÉ."""

    def setUp(self):
        self.co_a = _company('ntapi17-a', 'NTAPI17 A')
        self.co_b = _company('ntapi17-b', 'NTAPI17 B')

    def test_sequence_commence_a_un_et_croit(self):
        for attendu in (1, 2, 3):
            evenement = events_feed.enregistrer(
                self.co_a.id, EVENT_LEAD_CREATED, {'id': attendu})
            self.assertEqual(evenement.sequence, attendu)

    def test_sequence_independante_par_societe(self):
        events_feed.enregistrer(self.co_a.id, EVENT_LEAD_CREATED, {})
        events_feed.enregistrer(self.co_a.id, EVENT_LEAD_CREATED, {})
        premier_b = events_feed.enregistrer(
            self.co_b.id, EVENT_LEAD_CREATED, {})
        # La société B commence à 1 : elle ne peut pas déduire le volume de A.
        self.assertEqual(premier_b.sequence, 1)

    def test_sequence_ne_recule_jamais_apres_purge(self):
        """`count() + 1` donnerait un doublon ici — le plus-haut-utilisé, non."""
        for _ in range(3):
            events_feed.enregistrer(self.co_a.id, EVENT_LEAD_CREATED, {})
        ApiEvent.objects.filter(company=self.co_a, sequence__lt=3).delete()
        suivant = events_feed.enregistrer(self.co_a.id, EVENT_LEAD_CREATED, {})
        self.assertEqual(suivant.sequence, 4)

    def test_event_id_partage_avec_la_livraison_webhook(self):
        evenement = events_feed.enregistrer(
            self.co_a.id, EVENT_LEAD_CREATED, {}, event_id='abc-123')
        self.assertEqual(evenement.event_id, 'abc-123')


class Ntapi17AlimentationTests(TestCase):
    """Le flux est alimenté par les MÊMES signaux que les webhooks."""

    def setUp(self):
        self.co = _company('ntapi17-feed', 'NTAPI17 feed')

    def test_dispatch_alimente_le_flux_meme_sans_abonne(self):
        with patch('apps.publicapi.tasks.deliver_webhook.delay'):
            delivery.dispatch_event(
                self.co.id, EVENT_LEAD_CREATED, {'id': 7, 'nom': 'Test'})
        evenements = list(ApiEvent.objects.filter(company=self.co))
        self.assertEqual(len(evenements), 1)
        self.assertEqual(evenements[0].type, EVENT_LEAD_CREATED)
        self.assertEqual(evenements[0].payload['id'], 7)
        # `event_id` stable, posé par `ensure_event_id` : un consommateur qui
        # utilise LES DEUX canaux déduplique dessus.
        self.assertTrue(evenements[0].event_id)

    def test_sans_societe_rien_nest_journalise(self):
        delivery.dispatch_event(None, EVENT_LEAD_CREATED, {})
        self.assertEqual(ApiEvent.objects.count(), 0)


class Ntapi17CurseurTests(TestCase):
    """Le cœur du critère : `after=0` puis re-poll = uniquement du neuf."""

    def setUp(self):
        self.co = _company('ntapi17-cur', 'NTAPI17 curseur')
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='flux',
            scopes=[SCOPE_READ_EVENTS, SCOPE_READ_LEADS, SCOPE_READ_FACTURES])
        self.client_api = _key_client(self.raw)

    def _emettre(self, nb, event=EVENT_LEAD_CREATED):
        for i in range(nb):
            events_feed.enregistrer(self.co.id, event, {'i': i})

    def test_repoll_ne_renvoie_que_du_neuf_dans_lordre(self):
        self._emettre(3)
        premier = self.client_api.get('/api/public/v1/events/?after=0').json()
        sequences = [e['sequence'] for e in premier['results']]
        self.assertEqual(sequences, [1, 2, 3])
        self.assertEqual(premier['next_after'], 3)

        # Rien de neuf entre-temps : la page est vide, et le curseur du client
        # est PRÉSERVÉ (`next_after` None, jamais 0 — sinon il relirait tout).
        vide = self.client_api.get('/api/public/v1/events/?after=3').json()
        self.assertEqual(vide['results'], [])
        self.assertIsNone(vide['next_after'])

        # Deux évènements neufs : seuls ceux-là reviennent.
        self._emettre(2)
        suite = self.client_api.get('/api/public/v1/events/?after=3').json()
        self.assertEqual([e['sequence'] for e in suite['results']], [4, 5])

    def test_limite_respectee_et_bornee(self):
        self._emettre(5)
        page = self.client_api.get(
            '/api/public/v1/events/?after=0&limit=2').json()
        self.assertEqual(len(page['results']), 2)
        self.assertEqual(page['next_after'], 2)
        # Une limite délirante est ramenée au plafond, jamais servie telle quelle.
        plafonnee = self.client_api.get(
            '/api/public/v1/events/?after=0&limit=99999').json()
        self.assertEqual(plafonnee['limit'], events_feed.LIMITE_MAX)

    def test_parametres_invalides_renvoient_400(self):
        self.assertEqual(
            self.client_api.get(
                '/api/public/v1/events/?after=abc').status_code, 400)
        self.assertEqual(
            self.client_api.get(
                '/api/public/v1/events/?after=-1').status_code, 400)
        self.assertEqual(
            self.client_api.get(
                '/api/public/v1/events/?limit=0').status_code, 400)


class Ntapi17ScopesTests(TestCase):
    """Le flux n'est JAMAIS un contournement des scopes de lecture."""

    def setUp(self):
        self.co = _company('ntapi17-sc', 'NTAPI17 scopes')
        events_feed.enregistrer(self.co.id, EVENT_LEAD_CREATED, {'x': 1})
        events_feed.enregistrer(self.co.id, EVENT_FACTURE_PAID,
                                {'montant_ttc': 90000})
        events_feed.enregistrer(self.co.id, EVENT_TICKET_CREATED, {'x': 3})

    def _client(self, scopes):
        _key, raw = ApiKey.issue(company=self.co, label='k', scopes=scopes)
        return _key_client(raw)

    def test_sans_read_events_le_canal_est_ferme(self):
        resp = self._client([SCOPE_READ_LEADS]).get('/api/public/v1/events/')
        self.assertEqual(resp.status_code, 403)

    def test_read_events_seul_lit_un_flux_vide(self):
        resp = self._client([SCOPE_READ_EVENTS]).get('/api/public/v1/events/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], [])

    def test_chaque_evenement_exige_le_scope_de_sa_famille(self):
        resp = self._client(
            [SCOPE_READ_EVENTS, SCOPE_READ_LEADS]).get('/api/public/v1/events/')
        types = {e['type'] for e in resp.json()['results']}
        self.assertEqual(types, {EVENT_LEAD_CREATED})
        # La facture (montant réel) reste invisible sans `read:factures`.
        self.assertNotIn(EVENT_FACTURE_PAID, types)

    def test_evenement_sans_scope_de_famille_nest_jamais_renvoye(self):
        """`ticket.*` n'a aucun scope de lecture SAV : plutôt un flux
        incomplet et documenté qu'une escalade de privilège silencieuse."""
        resp = self._client([
            SCOPE_READ_EVENTS, SCOPE_READ_LEADS, SCOPE_READ_FACTURES,
        ]).get('/api/public/v1/events/')
        types = {e['type'] for e in resp.json()['results']}
        self.assertNotIn(EVENT_TICKET_CREATED, types)

    def test_aucune_fuite_cross_tenant(self):
        autre = _company('ntapi17-autre', 'NTAPI17 autre')
        events_feed.enregistrer(autre.id, EVENT_LEAD_CREATED, {'secret': 1})
        resp = self._client(
            [SCOPE_READ_EVENTS, SCOPE_READ_LEADS]).get('/api/public/v1/events/')
        for entree in resp.json()['results']:
            self.assertNotIn('secret', entree['payload'])


class Ntapi17RetentionTests(TestCase):
    """La rétention est bornée PAR SOCIÉTÉ par son plan (NTAPI7)."""

    def setUp(self):
        self.co = _company('ntapi17-ret', 'NTAPI17 rétention')

    def test_sans_plan_rien_nest_purge(self):
        import datetime

        from django.utils import timezone

        events_feed.enregistrer(self.co.id, EVENT_LEAD_CREATED, {})
        ApiEvent.objects.filter(company=self.co).update(
            created_at=timezone.now() - datetime.timedelta(days=400))
        self.assertEqual(
            events_feed.purger_evenements(timezone.now(), apply_=True), 0)
        self.assertEqual(ApiEvent.objects.filter(company=self.co).count(), 1)

    def test_plan_borne_la_retention(self):
        import datetime

        from django.utils import timezone

        from core.models import ApiUsagePlan

        ApiUsagePlan.objects.update_or_create(
            company=self.co, defaults={'retention_livraisons_jours': 30})
        events_feed.enregistrer(self.co.id, EVENT_LEAD_CREATED, {})
        recent = events_feed.enregistrer(self.co.id, EVENT_LEAD_CREATED, {})
        ApiEvent.objects.filter(company=self.co).exclude(pk=recent.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=90))
        purges = events_feed.purger_evenements(timezone.now(), apply_=True)
        self.assertEqual(purges, 1)
        self.assertEqual(ApiEvent.objects.filter(company=self.co).count(), 1)

    def test_dry_run_ne_supprime_rien(self):
        import datetime

        from django.utils import timezone

        from core.models import ApiUsagePlan

        ApiUsagePlan.objects.update_or_create(
            company=self.co, defaults={'retention_livraisons_jours': 30})
        events_feed.enregistrer(self.co.id, EVENT_LEAD_CREATED, {})
        ApiEvent.objects.filter(company=self.co).update(
            created_at=timezone.now() - datetime.timedelta(days=90))
        self.assertEqual(
            events_feed.purger_evenements(timezone.now(), apply_=False), 1)
        self.assertEqual(ApiEvent.objects.filter(company=self.co).count(), 1)
