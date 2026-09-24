"""CALX368 — webhook « calepinage simulé » (`calepinage.simule`).

Le service d'orchestration de la simulation
(``apps.calepinage.services.simulation``) annonce une simulation ABOUTIE sur
le bus ``core.events`` (``calepinage_simule``) ; ``apps.publicapi`` s'y abonne
et livre le webhook par le socle existant : un POST JSON signé HMAC avec son
horodatage — jamais un GET qui porterait les valeurs dans l'URL.

Les classes sans base (``SimpleTestCase``) tournent partout ; celles dont le
nom contient « EnBase » exigent la base de données et tournent en CI.
"""
import json
from unittest import mock

from django.apps import apps as django_apps
from django.test import SimpleTestCase, TestCase

from core import event_catalog, events

from . import calepinage_event_receivers as recepteurs
from . import delivery
from .constants import (
    ALL_EVENTS, EVENT_CALEPINAGE_SIMULE, EVENT_CALEPINAGE_VALIDE,
    EVENT_CHOICES, SCOPE_READ_CALEPINAGES,
)

#: Un résultat RÉELLEMENT simulé, à la forme du contrat
#: ``calepinage_simulation.json`` (``production.total``) plus les clés du
#: moteur que ``PublicCalepinageSerializer`` lit (``kwc``/``total_modules``).
#: ``plans`` et le document portent une géométrie qui ne doit jamais sortir.
RESULTAT_SIMULE = {
    'kwc': 6.6,
    'total_modules': 12,
    'plans': [{'surface': 'PAN-SECRET', 'modules': 12,
               'rangees': [[0, 0, 1.1, 1.7]]}],
    'production': {
        'total': {'p50_kwh': 10350.5, 'p75_kwh': 9900.0, 'p90_kwh': 9500.0,
                  'performance_ratio': 0.801},
    },
    'simulation': {'hash_entree': 'f' * 64, 'calcule_le': '2026-09-21T10:14:00Z'},
}

#: Les champs publiés par ``PublicCalepinageSerializer`` (CAL214) — la
#: charge utile ne peut en reprendre qu'un SOUS-ENSEMBLE, plus les deux clés
#: de production que la tâche nomme.
EN_PLUS_AUTORISEES = {'p50_kwh', 'performance_ratio'}


def _champs_du_serializer_public():
    from .public_serializers import PublicCalepinageSerializer
    return set(PublicCalepinageSerializer().fields)


def _modele_calepinage():
    return django_apps.get_model('calepinage', 'Calepinage')


class _Calepinage:
    """Le strict minimum qu'un abonné lit sur le pivot — aucun ORM."""

    def __init__(self, *, pk=41, company_id=7, resultat=None):
        self.pk = pk
        self.company_id = company_id
        self.titre = 'Toiture atelier'
        self.statut = 'brouillon'
        self.lead_id = 12
        self.client_id = None
        self.devis_id = 88
        self.appel_offre_id = None
        self.layout_hash = 'a' * 64
        self.version_moteur = '2026.09'
        self.roof_layout = {'zones': [{'label': 'GEOMETRIE-SECRETE'}]}
        self.resultat = resultat


# ═══════════════════════════════════════════════════════════════════════════
# 1. LE VOCABULAIRE — constante, libellé, scope, catalogue du bus
# ═══════════════════════════════════════════════════════════════════════════

class VocabulaireTests(SimpleTestCase):
    def test_la_constante_et_son_libelle(self):
        self.assertEqual(EVENT_CALEPINAGE_SIMULE, 'calepinage.simule')
        self.assertIn(EVENT_CALEPINAGE_SIMULE, ALL_EVENTS)
        libelles = dict(EVENT_CHOICES)
        self.assertTrue(libelles[EVENT_CALEPINAGE_SIMULE].strip())
        # Deux évènements distincts : valider n'est pas simuler.
        self.assertNotEqual(EVENT_CALEPINAGE_SIMULE, EVENT_CALEPINAGE_VALIDE)

    def test_le_flux_exige_le_scope_de_lecture_de_sa_famille(self):
        from .events_feed import SCOPE_PAR_EVENEMENT

        self.assertEqual(SCOPE_PAR_EVENEMENT[EVENT_CALEPINAGE_SIMULE],
                         SCOPE_READ_CALEPINAGES)

    def test_l_evenement_figure_a_la_reference_publique(self):
        from .docs import public_api_reference

        codes = {e['code']
                 for e in public_api_reference()['webhooks']['evenements']}
        self.assertIn(EVENT_CALEPINAGE_SIMULE, codes)

    def test_le_signal_du_bus_est_declare_et_catalogue(self):
        self.assertIsInstance(events.calepinage_simule,
                              type(events.devis_accepted))
        entree = event_catalog.entry('calepinage_simule')
        self.assertIsNotNone(entree)
        self.assertEqual(set(entree['payload']), {'calepinage', 'company_id'})

    def test_le_catalogue_colle_aux_kwargs_reels_de_l_emetteur(self):
        from core import event_coverage

        emis = event_coverage.emitter_payload_keys()
        self.assertEqual(emis.get('calepinage_simule'),
                         {'calepinage', 'company_id'})


# ═══════════════════════════════════════════════════════════════════════════
# 2. LA CHARGE UTILE — un sous-ensemble du public, jamais de géométrie/coût
# ═══════════════════════════════════════════════════════════════════════════

class ChargeUtileTests(SimpleTestCase):
    def test_les_cles_sont_celles_du_serializer_public_plus_la_production(self):
        charge = recepteurs.charge_utile_simulation(
            _Calepinage(resultat=RESULTAT_SIMULE))
        self.assertEqual(tuple(charge), recepteurs.CLES_CHARGE_SIMULE)
        hors_public = set(charge) - _champs_du_serializer_public()
        self.assertEqual(hors_public, EN_PLUS_AUTORISEES)

    def test_p50_et_ratio_de_performance_lus_du_resultat_reel(self):
        charge = recepteurs.charge_utile_simulation(
            _Calepinage(resultat=RESULTAT_SIMULE))
        self.assertEqual(charge['p50_kwh'], 10350.5)
        self.assertEqual(charge['performance_ratio'], 0.801)
        self.assertEqual(charge['kwc'], 6.6)
        self.assertEqual(charge['modules'], 12)
        self.assertEqual(charge['id'], 41)
        self.assertEqual(charge['devis_id'], 88)

    def test_rien_de_calcule_donne_null_jamais_zero(self):
        for resultat in (None, {}, {'production': {'total': {}}},
                         {'production': None},
                         {'production': {'total': {'p50_kwh': None,
                                                   'performance_ratio': None}}},
                         {'production': {'total': {'p50_kwh': True,
                                                   'performance_ratio': 'x'}}}):
            with self.subTest(resultat=resultat):
                charge = recepteurs.charge_utile_simulation(
                    _Calepinage(resultat=resultat))
                self.assertIsNone(charge['p50_kwh'])
                self.assertIsNone(charge['performance_ratio'])
                self.assertIsNone(charge['kwc'])
                self.assertIsNone(charge['modules'])

    def test_ni_geometrie_ni_cout(self):
        charge = recepteurs.charge_utile_simulation(
            _Calepinage(resultat=RESULTAT_SIMULE))
        texte = json.dumps(charge)
        self.assertNotIn('PAN-SECRET', texte)
        self.assertNotIn('GEOMETRIE-SECRETE', texte)
        for interdite in ('roof_layout', 'plans', 'rangees', 'resultat',
                          'liens'):
            self.assertNotIn(interdite, charge)
        for cle in charge:
            self.assertFalse(cle.startswith(('prix', 'cout', 'marge')), cle)


# ═══════════════════════════════════════════════════════════════════════════
# 3. L'ABONNÉ — branché sur le bus, par le registre, rien sans le module
# ═══════════════════════════════════════════════════════════════════════════

class AbonneTests(SimpleTestCase):
    def test_le_signal_du_modele_livre_calepinage_simule(self):
        pivot = _Calepinage(resultat=RESULTAT_SIMULE)
        with mock.patch.object(delivery, 'dispatch_event') as envoi:
            events.calepinage_simule.send(
                sender=_modele_calepinage(), calepinage=pivot,
                company_id=7)
        envoi.assert_called_once()
        args, _kwargs = envoi.call_args
        self.assertEqual(args[0], 7)
        self.assertEqual(args[1], EVENT_CALEPINAGE_SIMULE)
        self.assertEqual(args[2]['p50_kwh'], 10350.5)

    def test_un_autre_emetteur_ne_declenche_rien(self):
        """L'abonnement est borné au modèle résolu par le registre."""
        with mock.patch.object(delivery, 'dispatch_event') as envoi:
            events.calepinage_simule.send(
                sender=_Calepinage, calepinage=_Calepinage(), company_id=7)
        envoi.assert_not_called()

    def test_sans_societe_rien_ne_part(self):
        with mock.patch.object(delivery, 'dispatch_event') as envoi:
            events.calepinage_simule.send(
                sender=_modele_calepinage(),
                calepinage=_Calepinage(company_id=None), company_id=None)
        envoi.assert_not_called()

    def test_un_echec_de_livraison_ne_remonte_jamais(self):
        with mock.patch.object(delivery, 'dispatch_event',
                               side_effect=RuntimeError('broker')),                 self.assertLogs(recepteurs.logger, 'ERROR') as journal:
            recepteurs.calepinage_simule_recu(
                None, calepinage=_Calepinage(), company_id=7)
        self.assertIn(EVENT_CALEPINAGE_SIMULE, journal.output[0])

    def test_sans_module_calepinage_rien_n_est_branche(self):
        with mock.patch.object(recepteurs, '_calepinage_model',
                               return_value=None), \
                mock.patch.object(events.calepinage_simule,
                                  'connect') as branche:
            self.assertFalse(recepteurs.connecter_simulation())
        branche.assert_not_called()
        with mock.patch.object(recepteurs, '_variante_model',
                               return_value=None), \
                mock.patch.object(recepteurs,
                                  'connecter_simulation') as simulation:
            recepteurs.connect()
        simulation.assert_not_called()

    def test_le_modele_est_resolu_par_le_registre_jamais_importe(self):
        import ast
        import inspect

        arbre = ast.parse(inspect.getsource(recepteurs))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                self.assertFalse((noeud.module or '').startswith(
                    'apps.calepinage'), noeud.module)
            if isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    self.assertFalse(alias.name.startswith('apps.calepinage'))


# ═══════════════════════════════════════════════════════════════════════════
# 4. L'ÉMETTEUR — le service de simulation annonce seulement ce qu'il écrit
# ═══════════════════════════════════════════════════════════════════════════

class EmetteurTests(SimpleTestCase):
    def test_annoncer_envoie_le_pivot_et_sa_societe(self):
        from apps.calepinage.services import simulation

        pivot = _Calepinage(resultat=RESULTAT_SIMULE)
        with mock.patch.object(events.calepinage_simule, 'send') as envoi:
            simulation._annoncer_simulation(pivot)
        envoi.assert_called_once_with(
            sender=_Calepinage, calepinage=pivot, company_id=7)

    def test_un_pivot_jamais_enregistre_n_annonce_rien(self):
        from apps.calepinage.services import simulation

        with mock.patch.object(events.calepinage_simule, 'send') as envoi:
            simulation._annoncer_simulation(_Calepinage(pk=None))
        envoi.assert_not_called()

    def test_un_abonne_qui_leve_ne_casse_pas_la_simulation(self):
        from apps.calepinage.services import simulation

        with mock.patch.object(events.calepinage_simule, 'send',
                               side_effect=RuntimeError('abonné')),                 self.assertLogs(simulation.logger, 'ERROR') as journal:
            simulation._annoncer_simulation(_Calepinage())
        self.assertIn('calepinage_simule', journal.output[0])

    def test_un_calcul_a_blanc_n_annonce_rien(self):
        from apps.calepinage.tests.test_calx5_simulation import _simuler

        with mock.patch.object(events.calepinage_simule, 'send') as envoi:
            rendu = _simuler(enregistrer=False)
        self.assertFalse(rendu['deja_calcule'])
        envoi.assert_not_called()

    def test_un_deja_calcule_n_annonce_rien(self):
        from apps.calepinage.tests.test_calx5_simulation import (
            _Calepinage as PivotSansBase, _simuler,
        )

        empreinte = _simuler()['hash_entree']
        pivot = PivotSansBase(resultat={'simulation': {
            'hash_entree': empreinte, 'calcule_le': '2026-09-21T10:14:00Z'}})
        with mock.patch.object(events.calepinage_simule, 'send') as envoi:
            rendu = _simuler(pivot, enregistrer=True)
        self.assertTrue(rendu['deja_calcule'])
        envoi.assert_not_called()

    def test_une_simulation_enregistree_annonce_une_fois(self):
        from apps.calepinage.services import simulation
        from apps.calepinage.tests.test_calx5_simulation import (
            _Calepinage as PivotSansBase, _simuler,
        )

        # Le pivot du harnais CALX5, mais ENREGISTRÉ (``pk``) : la fusion est
        # interceptée (aucune base), la recherche d'un fichier météo aussi.
        pivot = PivotSansBase()
        pivot.pk = 41
        pivot.company_id = 7
        with mock.patch.object(simulation, '_serie_meteo_deposee',
                               return_value=None), \
                mock.patch.object(simulation, '_fusionner') as fusion, \
                mock.patch.object(events.calepinage_simule, 'send') as envoi:
            rendu = _simuler(pivot, enregistrer=True)
        self.assertFalse(rendu['deja_calcule'])
        fusion.assert_called_once()
        envoi.assert_called_once()
        self.assertIs(envoi.call_args.kwargs['calepinage'], pivot)


# ═══════════════════════════════════════════════════════════════════════════
# 5. LE TRANSPORT — un POST signé et horodaté, jamais un GET à l'URL chargée
# ═══════════════════════════════════════════════════════════════════════════

class _Webhook:
    target_url = 'https://integration.example.test/hooks/taqinor'
    secret = 'secret-calx368'


class TransportTests(SimpleTestCase):
    def setUp(self):
        garde = mock.patch.object(delivery, 'validate_webhook_target_url',
                                  side_effect=lambda url: url)
        garde.start()
        self.addCleanup(garde.stop)

    def _livrer(self):
        capture = {}

        def faux_post(url, content=None, headers=None, timeout=None):
            capture.update(url=url, content=content, headers=headers)
            return mock.Mock(status_code=200)

        charge = delivery.ensure_event_id(recepteurs.charge_utile_simulation(
            _Calepinage(resultat=RESULTAT_SIMULE)))
        with mock.patch.object(delivery.httpx, 'post',
                               side_effect=faux_post) as post, \
                mock.patch.object(delivery.httpx, 'get',
                                  side_effect=AssertionError('GET interdit'),
                                  create=True) as get:
            issue = delivery._send(_Webhook(), EVENT_CALEPINAGE_SIMULE,
                                   charge)
        return issue, capture, post, get, charge

    def test_la_livraison_est_un_post_avec_un_corps(self):
        issue, capture, post, get, charge = self._livrer()
        self.assertEqual(issue[0], 'success')
        post.assert_called_once()
        get.assert_not_called()
        corps = json.loads(capture['content'])
        self.assertEqual(corps['p50_kwh'], charge['p50_kwh'])
        self.assertEqual(corps['performance_ratio'], 0.801)

    def test_aucune_valeur_dans_la_chaine_de_requete(self):
        _issue, capture, _post, _get, _charge = self._livrer()
        self.assertEqual(capture['url'], _Webhook.target_url)
        self.assertNotIn('?', capture['url'])
        self.assertNotIn('10350', capture['url'])

    def test_signature_hmac_horodatee_verifiable(self):
        _issue, capture, _post, _get, _charge = self._livrer()
        entetes = capture['headers']
        self.assertEqual(entetes[delivery.EVENT_HEADER],
                         EVENT_CALEPINAGE_SIMULE)
        horodatage = entetes[delivery.TIMESTAMP_HEADER]
        self.assertTrue(horodatage.isdigit())
        v2 = entetes[delivery.SIGNATURE_HEADER_V2]
        self.assertRegex(v2, r'^t=\d+,v1=[0-9a-f]{64}$')
        self.assertTrue(delivery.verify_signature_v2(
            _Webhook.secret, capture['content'], v2,
            now=int(horodatage)))
        # Un corps altéré ne vérifie plus : la signature couvre les valeurs.
        altere = capture['content'].replace(b'10350.5', b'99999.9')
        self.assertFalse(delivery.verify_signature_v2(
            _Webhook.secret, altere, v2, now=int(horodatage)))

    def test_la_docstring_dit_pourquoi_pas_le_get_d_aurora(self):
        texte = recepteurs.__doc__
        self.assertIn('https://help.aurorasolar.com/hc/en-us/articles/'
                      '17426531448083-CRM-Checklist-for-Aurora-API-'
                      'Integrations', texte)
        self.assertIn('GET', texte)
        self.assertIn('query string', texte)
        self.assertIn('Nous ne le suivons PAS', texte)
        self.assertIn('X-Taqinor-Signature-V2', texte)
        self.assertIn('X-Taqinor-Timestamp', texte)


# ═══════════════════════════════════════════════════════════════════════════
# 6. DE BOUT EN BOUT, EN BASE (CI) — le socle réel de livraison
# ═══════════════════════════════════════════════════════════════════════════

class LivraisonEnBaseTests(TestCase):
    def setUp(self):
        from authentication.models import Company

        from .models import Webhook

        self.co, _ = Company.objects.get_or_create(
            slug='pa-calx368', defaults={'nom': 'PA CALX368'})
        self.cal = _modele_calepinage().objects.create(
            company=self.co, lead_id=1, titre='Toiture simulée',
            resultat=RESULTAT_SIMULE)
        self.webhook = Webhook.objects.create(
            company=self.co, label='intégration',
            target_url='https://integration.example.test/hooks/taqinor',
            secret='secret-calx368', events=[EVENT_CALEPINAGE_SIMULE],
            enabled=True)
        garde = mock.patch.object(delivery, 'validate_webhook_target_url',
                                  side_effect=lambda url: url)
        garde.start()
        self.addCleanup(garde.stop)

    def test_le_service_livre_un_post_signe_par_le_socle(self):
        from apps.calepinage.services import simulation

        from . import tasks
        from .models import ApiEvent, Webhook, WebhookDelivery

        capture = {}

        def faux_post(url, content=None, headers=None, timeout=None):
            capture.update(url=url, content=content, headers=headers)
            return mock.Mock(status_code=200)

        def livrer_tout_de_suite(webhook_id, event, payload):
            delivery._deliver_one(Webhook.objects.get(pk=webhook_id), event,
                                  payload)

        with mock.patch.object(tasks.deliver_webhook, 'delay',
                               side_effect=livrer_tout_de_suite), \
                mock.patch.object(delivery.httpx, 'post',
                                  side_effect=faux_post) as post, \
                mock.patch.object(delivery.httpx, 'get',
                                  side_effect=AssertionError('GET interdit'),
                                  create=True) as get:
            simulation._annoncer_simulation(self.cal)

        post.assert_called_once()
        get.assert_not_called()
        self.assertEqual(capture['url'], self.webhook.target_url)
        corps = json.loads(capture['content'])
        self.assertEqual(corps['id'], self.cal.pk)
        self.assertEqual(corps['p50_kwh'], 10350.5)
        self.assertTrue(corps['event_id'])
        entetes = capture['headers']
        self.assertTrue(delivery.verify_signature_v2(
            'secret-calx368', capture['content'],
            entetes[delivery.SIGNATURE_HEADER_V2],
            now=int(entetes[delivery.TIMESTAMP_HEADER])))
        livraison = WebhookDelivery.objects.get(webhook=self.webhook)
        self.assertEqual(livraison.event, EVENT_CALEPINAGE_SIMULE)
        self.assertEqual(livraison.status, WebhookDelivery.Statut.SUCCESS)
        # Le flux PULL reçoit le même évènement (NTAPI17).
        self.assertTrue(ApiEvent.objects.filter(
            company=self.co, type=EVENT_CALEPINAGE_SIMULE).exists())

    def test_un_webhook_non_abonne_ne_recoit_rien(self):
        from apps.calepinage.services import simulation

        from . import tasks

        self.webhook.events = [EVENT_CALEPINAGE_VALIDE]
        self.webhook.save(update_fields=['events'])
        with mock.patch.object(tasks.deliver_webhook, 'delay') as envoi:
            simulation._annoncer_simulation(self.cal)
        envoi.assert_not_called()
