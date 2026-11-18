"""TCH95 — Jetons d'accès (reference/api.md §0 « J:x », §3.4 ; donnees.md §2.14, §5, invariant 20).

`jetons/` (session) : `jeton.json` (clair rendu UNE fois, l'ancien du même usage révoqué),
`jetons_liste.json` (jamais l'empreinte ni le clair), révocation, 403 sous l'en-tête assistant, 400 à
clé racine `error`. `JetonAccesAuthentication` : le jeton de SON usage seulement ; un jeton inconnu,
d'un autre usage, révoqué, d'un compte désactivé, portail, sans `taches_voir` ou sans rôle fin, d'une
société suspendue ou dont le module est éteint répondent EXACTEMENT pareil (401 neutre ; 404 neutre
pour le flux) ; multi-sociétés : la société du jeton, et le rôle de CETTE société ; aucun clair ni
empreinte dans un journal (500 du flux compris) ; débit par jeton (429).

Base requise (`TestCase`) : joué par la CI. Les routes capture, tuile et flux sont construites par
TCH96 et TCH97 : ici, seul ce qui se passe AVANT leur gestionnaire est vérifié (authentification,
débit), jamais leur corps de succès.
"""
import contextlib
import datetime
import hashlib
import io
import json
import logging
import os
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.handlers.wsgi import WSGIHandler
from django.core.signals import request_finished, request_started
from django.db import close_old_connections
from django.test import RequestFactory, TestCase, override_settings
from django.utils.module_loading import import_string
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.test import APIClient

from apps.roles.models import Role
from apps.taches.auth_jeton import JetonCapture, JetonFlux, JetonTuile, emettre_jeton
from apps.taches.models.presence import JetonAcces
from apps.taches.tests import fabriques
from apps.taches.tests.test_api_saisie import champs
from apps.taches.throttles import ThrottleTuile
from apps.taches.views.base import exemple_de
from apps.taches.views.presence import FluxVue
from authentication.models import AppartenanceSociete
from core import monitoring
from core.logging_ext import build_logging_config
from core.models import ModuleToggle

PREFIXE = '/api/django/taches/'
URL_JETONS = PREFIXE + 'jetons/'
INCONNU = {'capture': 'tqc_' + 'x' * 43, 'flux': 'tqf_' + 'x' * 43, 'tuile': 'tqt_' + 'x' * 43}
T0 = datetime.datetime(2026, 11, 17, 9, 0, tzinfo=datetime.timezone.utc)


def _empreinte(clair):
    return hashlib.sha256(clair.encode('utf-8')).hexdigest()


def _neutre(reponse):
    """Ce qu'un refus montre : statut, en-tête `WWW-Authenticate`, corps sans `request_id`."""
    corps = reponse.json()
    erreur = {cle: valeur for cle, valeur in (corps.get('error') or {}).items() if cle != 'request_id'}
    return (reponse.status_code, reponse.get('WWW-Authenticate'),
            {**{cle: valeur for cle, valeur in corps.items() if cle != 'error'}, 'error': erreur})


@contextlib.contextmanager
def journaux():
    """Tout enregistrement de journal émis pendant le bloc, quel que soit le niveau ou le logger
    (aucun n'est écrit ailleurs) : son dictionnaire complet et sa pile formatée."""
    lignes = []

    def garder(_logger, record):
        pile = logging.Formatter().formatException(record.exc_info) if record.exc_info else ''
        lignes.append(f'{vars(record)!r} {pile}')

    with mock.patch.object(logging.Logger, 'isEnabledFor', return_value=True), \
            mock.patch.object(logging.Logger, 'handle', autospec=True, side_effect=garder):
        yield lignes


@contextlib.contextmanager
def journal_json():
    """Ce qu'écrit le journal de `LOG_FORMAT=json` : les filtres et le formateur de `build_logging_config`,
    appliqués à TOUT enregistrement émis (quel que soit son niveau ou son logger), après la fabrique
    d'enregistrements et le contexte de requête, comme en production."""
    config = build_logging_config()
    console = config['handlers']['console_json']
    sortie = io.StringIO()
    handler = logging.StreamHandler(sortie)
    for nom in console['filters']:
        handler.addFilter(import_string(config['filters'][nom]['()'])())
    handler.setFormatter(import_string(config['formatters'][console['formatter']]['()'])())
    with mock.patch.object(logging.Logger, 'isEnabledFor', return_value=True), \
            mock.patch.object(logging.Logger, 'callHandlers', autospec=True,
                              side_effect=lambda _logger, record: handler.handle(record)):
        yield sortie


@contextlib.contextmanager
def sentry_capture():
    """`core.monitoring.init_sentry()` réel (intégrations Django et journaux, traces à 100 %), seul son
    transport remplacé : rend les charges JSON que Sentry aurait envoyées. Coupé à la sortie."""
    import sentry_sdk
    from sentry_sdk.transport import Transport
    charges = []

    class Capteur(Transport):
        def capture_envelope(self, envelope):
            charges.extend(item.payload.json for item in envelope.items if item.payload.json is not None)

        def flush(self, timeout, callback=None):
            return None

        def kill(self):
            return None

    vrai_init = sentry_sdk.init
    with mock.patch.dict(os.environ, {'SENTRY_DSN': 'http://cle@localhost/1', 'SENTRY_TRACES_SAMPLE_RATE': '1'}), \
            mock.patch.object(monitoring, '_INITIALISE', False), \
            mock.patch.object(sentry_sdk, 'init', lambda **options: vrai_init(transport=Capteur, **options)):
        try:
            assert monitoring.init_sentry()
            yield charges
            sentry_sdk.flush()
        finally:
            vrai_init(dsn='')


def appel_wsgi(chemin, methode='get', **options):
    """La requête par `WSGIHandler` (là où Sentry pose `request.url`) ; rend le statut."""
    environ = getattr(RequestFactory(), methode)(chemin, **options).environ
    statut = {}

    def start_response(ligne, _entetes, exc_info=None):
        statut['ligne'] = ligne

    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    try:
        reponse = WSGIHandler()(environ, start_response)
        b''.join(reponse)
        reponse.close()
    finally:
        request_started.connect(close_old_connections)
        request_finished.connect(close_old_connections)
    return int(statut['ligne'].split()[0])


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('jt-a')
        cls.b = fabriques.societe('jt-b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.u2 = fabriques.compte(cls.a, nom='u2')

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.api = APIClient()
        self.api.force_authenticate(self.u1)

    def _porteur(self, clair):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {clair}')
        return api


class JetonsApiTests(_Base):
    """`jetons/` et `jetons/{id}/revoquer/` (session)."""

    def _creer(self, usage, **corps):
        return self.api.post(URL_JETONS, {'usage': usage, **corps}, format='json')

    def test_creer_rend_jeton_json_et_le_clair_une_seule_fois(self):
        reponse = self._creer('flux', libelle='iPhone')
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse['Cache-Control'], 'no-store')
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('jeton')))
        clair = corps['jeton']
        self.assertTrue(clair.startswith('tqf_'))
        self.assertEqual(corps['prefixe'], clair[:8])
        self.assertEqual((corps['usage'], corps['libelle']), ('flux', 'iPhone'))
        self.assertIsNone(corps['revoque_le'])
        self.assertTrue(corps['url'].endswith(f'{PREFIXE}flux/{clair}.ics'))
        self.assertEqual(corps['webcal'], 'webcal://' + corps['url'].split('://', 1)[1])
        jeton = JetonAcces.objects.get(pk=corps['id'])
        self.assertEqual((jeton.company_id, jeton.proprietaire_id), (self.a.pk, self.u1.pk))
        self.assertEqual(jeton.jeton_hash, _empreinte(clair))
        self.assertNotIn(clair, repr(list(JetonAcces.objects.values_list())), 'le clair est stocké')

    def test_adresse_de_la_capture_et_de_la_tuile_sans_le_jeton(self):
        capture = self._creer('capture').json()
        self.assertTrue(capture['url'].endswith(f'{PREFIXE}capture/?reponse=texte'))
        self.assertIsNone(capture['webcal'])
        tuile = self._creer('tuile').json()
        self.assertTrue(tuile['url'].endswith(f'{PREFIXE}tuile/'))
        self.assertIsNone(tuile['webcal'])
        for corps in (capture, tuile):
            self.assertNotIn(corps['jeton'], corps['url'])

    def test_liste_jetons_liste_json_sans_empreinte_ni_clair(self):
        clairs = [self._creer(usage).json()['jeton'] for usage in ('flux', 'capture')]
        fabriques.jeton(self.u2, 'flux')
        reponse = self.api.get(URL_JETONS)
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertEqual(set(corps), set(exemple_de('jetons_liste')))
        cles = set(exemple_de('jetons_liste')['results'][0])
        self.assertEqual(len(corps['results']), 2, 'un jeton d\'un collègue est servi')
        for ligne in corps['results']:
            self.assertEqual(set(ligne), cles)
        for clair in clairs:
            self.assertNotIn(clair, reponse.content.decode())
            self.assertNotIn(_empreinte(clair), reponse.content.decode())

    def test_un_nouveau_jeton_revoque_l_ancien_du_meme_usage_seulement(self):
        premier = self._creer('flux').json()
        tuile = self._creer('tuile').json()
        second = self._creer('flux').json()
        etats = dict(JetonAcces.objects.values_list('pk', 'revoque_le'))
        self.assertIsNotNone(etats[premier['id']])
        self.assertIsNone(etats[second['id']])
        self.assertIsNone(etats[tuile['id']])
        liste = [ligne['id'] for ligne in self.api.get(URL_JETONS).json()['results']]
        self.assertEqual(liste[-1], premier['id'], 'les actifs passent avant les révoqués')
        self.assertEqual(set(liste), {premier['id'], second['id'], tuile['id']})
        refus = JetonFlux()
        with self.assertRaises(NotFound):
            refus.authenticate(SimpleNamespace(parser_context={'kwargs': {'jeton': premier['jeton']}}))

    def test_clair_suivi_d_un_saut_de_ligne_refuse_sans_lecture(self):
        """Revue F3 #8 (jumeau de `_HEURE`) : `FORME_CLAIR` finissait par `$`, qui accepte un saut de
        ligne final (`…%0A.ics` dans l'adresse du flux) : refusé par sa FORME, avant toute lecture."""
        _jeton, clair = fabriques.jeton(self.u1, 'flux')
        with self.assertNumQueries(0), self.assertRaises(NotFound):
            JetonFlux().authenticate(SimpleNamespace(parser_context={'kwargs': {'jeton': clair + '\n'}}))

    def test_revoquer(self):
        jeton, clair = fabriques.jeton(self.u1, 'tuile')
        url = f'{URL_JETONS}{jeton.pk}/revoquer/'
        self.assertEqual(self.api.post(url).status_code, 204)
        jeton.refresh_from_db()
        revoque_le = jeton.revoque_le
        self.assertIsNotNone(revoque_le)
        self.assertEqual(self.api.post(url).status_code, 204)  # naturelle : rien ne change
        jeton.refresh_from_db()
        self.assertEqual(jeton.revoque_le, revoque_le)
        self.assertEqual(self._porteur(clair).get(PREFIXE + 'tuile/').status_code, 401)

    def test_revoquer_le_jeton_d_un_autre_compte_repond_comme_un_inconnu(self):
        sien, _clair = fabriques.jeton(self.u2, 'tuile')
        autre = self.api.post(f'{URL_JETONS}{sien.pk}/revoquer/')
        inconnu = self.api.post(f'{URL_JETONS}2000000000/revoquer/')
        self.assertEqual(_neutre(autre), _neutre(inconnu))
        self.assertEqual(autre.status_code, 404)
        sien.refresh_from_db()
        self.assertIsNone(sien.revoque_le)

    def test_400_au_champ_avec_l_enveloppe_error(self):
        for corps, attendu in (({'usage': 'agenda'}, {'usage': ['Valeur inconnue.']}),
                               ({}, {'usage': ['Requis.']}),
                               ({'usage': 'flux', 'libelle': 'x' * 61}, {'libelle': ['60 caractères au plus.']})):
            with self.subTest(corps=corps):
                reponse = self.api.post(URL_JETONS, corps, format='json')
                self.assertEqual(reponse.status_code, 400)
                self.assertIn('error', reponse.json())
                self.assertEqual(champs(reponse.json()), attendu)
        self.assertFalse(JetonAcces.objects.exists())

    def test_jamais_sous_l_entete_assistant(self):
        jeton, _clair = fabriques.jeton(self.u1, 'flux')
        relais = APIClient(HTTP_X_TAQINOR_ASSISTANT='1')
        relais.force_authenticate(self.u1)
        reponses = {
            'liste': relais.get(URL_JETONS),
            'création': relais.post(URL_JETONS, {'usage': 'tuile'}, format='json'),
            'révocation': relais.post(f'{URL_JETONS}{jeton.pk}/revoquer/'),
        }
        for nom, reponse in reponses.items():
            with self.subTest(route=nom):
                self.assertEqual(reponse.status_code, 403)
        jeton.refresh_from_db()
        self.assertIsNone(jeton.revoque_le)
        self.assertEqual(JetonAcces.objects.count(), 1)


class AuthentificationTests(_Base):
    """`JetonAccesAuthentication` : admis, refus neutres, multi-sociétés, `dernier_usage_le`."""

    def _entete(self, clair):
        return RequestFactory().get('/', HTTP_AUTHORIZATION=f'Bearer {clair}')

    def _compte(self, nom, societe=None, **champs_compte):
        compte = fabriques.compte(societe or self.a, nom=nom)
        for champ, valeur in champs_compte.items():
            setattr(compte, champ, valeur)
        compte.save()
        return compte

    def test_jeton_actif_authentifie_son_proprietaire_dans_sa_societe(self):
        jeton, clair = fabriques.jeton(self.u1, 'tuile')
        compte, auth = JetonTuile().authenticate(self._entete(clair))
        self.assertEqual((compte.pk, compte.company_id, auth.pk), (self.u1.pk, self.a.pk, jeton.pk))
        jeton.refresh_from_db()
        self.assertIsNotNone(jeton.dernier_usage_le)

    def test_dernier_usage_ecrit_au_plus_une_fois_par_minute(self):
        jeton, clair = fabriques.jeton(self.u1, 'capture')
        for decalage, attendu in ((0, T0), (30, T0), (61, T0 + datetime.timedelta(seconds=61))):
            with self.subTest(decalage=decalage), \
                    mock.patch.object(timezone, 'now', return_value=T0 + datetime.timedelta(seconds=decalage)):
                JetonCapture().authenticate(self._entete(clair))
                jeton.refresh_from_db()
                self.assertEqual(jeton.dernier_usage_le, attendu)

    def _refus_neutres(self):
        """`(nom, clair de capture)` de chaque compte ou jeton qui doit être refusé."""
        inactif = self._compte('inactif', is_active=False)
        portail = self._compte('portail', portee=get_user_model().PORTEE_PORTAIL_CLIENT)
        sans_droit = fabriques.compte(self.a, voir=False, nom='sansdroit')
        sans_role = get_user_model().objects.create_user(
            username='sansrole@jt-a', password=None, company=self.a,
            role_legacy=get_user_model().ROLE_RESPONSABLE)
        suspendue = fabriques.societe('jt-susp')
        de_la_suspendue = fabriques.compte(suspendue, nom='susp')
        suspendue.actif = False
        suspendue.save()
        eteinte = fabriques.societe('jt-off')
        de_l_eteinte = fabriques.compte(eteinte, nom='off')
        ModuleToggle.objects.create(company=eteinte, module='taches', actif=False)
        revoque, clair_revoque = fabriques.jeton(self.u2, 'capture')
        revoque.revoque_le = timezone.now()
        revoque.save()
        return [
            ('jeton flux', fabriques.jeton(self.u1, 'flux')[1]),
            ('jeton tuile', fabriques.jeton(self.u1, 'tuile')[1]),
            ('révoqué', clair_revoque),
            ('compte désactivé', fabriques.jeton(inactif, 'capture')[1]),
            ('compte portail', fabriques.jeton(portail, 'capture')[1]),
            ('rôle sans taches_voir', fabriques.jeton(sans_droit, 'capture')[1]),
            ('compte sans rôle fin', fabriques.jeton(sans_role, 'capture')[1]),
            ('société suspendue', fabriques.jeton(de_la_suspendue, 'capture')[1]),
            ('module éteint', fabriques.jeton(de_l_eteinte, 'capture')[1]),
        ]

    def test_capture_refus_identique_a_un_jeton_inconnu(self):
        """Preuve : un jeton `flux` sur `capture/` → 401 identique à un inconnu ; compte sans rôle fin →
        401 ; aucun refus ne dit pourquoi."""
        cas = self._refus_neutres()
        reference = _neutre(self._porteur(INCONNU['capture']).post(PREFIXE + 'capture/', {}, format='json'))
        self.assertEqual(reference[0], 401)
        self.assertTrue(reference[1].startswith('Bearer'))
        for nom, clair in cas:
            with self.subTest(cas=nom):
                reponse = self._porteur(clair).post(PREFIXE + 'capture/', {}, format='json')
                self.assertEqual(_neutre(reponse), reference)
        for nom, clair in cas:
            with self.subTest(cas=nom, direct=True), self.assertRaises(AuthenticationFailed):
                JetonCapture().authenticate(self._entete(clair))

    def test_tuile_refuse_un_jeton_d_un_autre_usage_comme_un_inconnu(self):
        reference = _neutre(self._porteur(INCONNU['tuile']).get(PREFIXE + 'tuile/'))
        self.assertEqual(reference[0], 401)
        for usage in ('capture', 'flux'):
            clair = fabriques.jeton(self.u1, usage)[1]
            with self.subTest(usage=usage):
                self.assertEqual(_neutre(self._porteur(clair).get(PREFIXE + 'tuile/')), reference)

    def test_flux_refus_404_neutre_et_no_store(self):
        revoque, clair_revoque = fabriques.jeton(self.u2, 'flux')
        revoque.revoque_le = timezone.now()
        revoque.save()
        reference = APIClient().get(f'{PREFIXE}flux/{INCONNU["flux"]}.ics')
        self.assertEqual(reference.status_code, 404)
        self.assertEqual(reference['Cache-Control'], 'no-store')
        self.assertNotIn('WWW-Authenticate', reference)
        for nom, clair in (('jeton capture', fabriques.jeton(self.u1, 'capture')[1]),
                           ('jeton tuile', fabriques.jeton(self.u1, 'tuile')[1]),
                           ('révoqué', clair_revoque), ('mal formé', 'tqf_court')):
            with self.subTest(cas=nom):
                reponse = APIClient().get(f'{PREFIXE}flux/{clair}.ics')
                self.assertEqual(_neutre(reponse), _neutre(reference))
                self.assertEqual(reponse['Cache-Control'], 'no-store')

    def test_un_jeton_valide_passe_l_authentification(self):
        """Témoin des refus : le bon jeton n'est refusé sur aucune des trois routes."""
        capture = self._porteur(fabriques.jeton(self.u1, 'capture')[1]).post(PREFIXE + 'capture/', {}, format='json')
        tuile = self._porteur(fabriques.jeton(self.u1, 'tuile')[1]).get(PREFIXE + 'tuile/')
        flux = APIClient().get(f'{PREFIXE}flux/{fabriques.jeton(self.u1, "flux")[1]}.ics')
        self.assertNotEqual(capture.status_code, 401)
        self.assertNotEqual(tuile.status_code, 401)
        self.assertNotIn(flux.status_code, (401, 404))

    def test_multi_societes_la_societe_et_le_role_du_jeton(self):
        multi = fabriques.compte(self.a, nom='multi')
        role_b = Role.objects.create(company=self.b, nom='Test tâches B', permissions=['taches_voir'])
        lien = AppartenanceSociete.objects.create(user=multi, company=self.b, role=role_b)
        multi.company = self.b  # société ACTIVE posée en mémoire, comme l'authentification par cookie
        jeton_b, clair_b = emettre_jeton(multi, 'tuile')
        self.assertEqual(jeton_b.company_id, self.b.pk)
        compte, _auth = JetonTuile().authenticate(self._entete(clair_b))
        self.assertEqual((compte.pk, compte.company_id, compte.role_id), (multi.pk, self.b.pk, role_b.pk))
        _jeton_a, clair_a = fabriques.jeton(get_user_model().objects.get(pk=multi.pk), 'tuile')
        compte, _auth = JetonTuile().authenticate(self._entete(clair_a))
        self.assertEqual(compte.company_id, self.a.pk)
        relu = get_user_model().objects.get(pk=multi.pk)
        self.assertEqual(relu.company_id, self.a.pk, 'la société d\'attache a été écrite')
        lien.role = None
        lien.save()
        with self.assertRaises(AuthenticationFailed):
            JetonTuile().authenticate(self._entete(clair_b))
        lien.delete()
        with self.assertRaises(AuthenticationFailed):
            JetonTuile().authenticate(self._entete(clair_b))


class JournauxEtDebitsTests(_Base):
    """Aucun jeton journalisé ; débits par jeton."""

    def test_aucun_clair_ni_empreinte_dans_un_journal(self):
        with journaux() as lignes:
            clairs = [self.api.post(URL_JETONS, {'usage': usage}, format='json').json()['jeton']
                      for usage in ('capture', 'flux', 'tuile')]
            capture, flux, tuile = clairs
            self._porteur(flux).post(PREFIXE + 'capture/', {}, format='json')
            self._porteur(capture).post(PREFIXE + 'capture/', {}, format='json')
            self._porteur(capture).get(PREFIXE + 'tuile/')
            self._porteur(tuile).get(PREFIXE + 'tuile/')
            APIClient().get(f'{PREFIXE}flux/{capture}.ics')
            APIClient().get(f'{PREFIXE}flux/{flux}.ics')
            APIClient().get(f'{PREFIXE}flux/{INCONNU["flux"]}.ics')
        self.assertTrue(any('refusé' in ligne for ligne in lignes), 'le collecteur ne voit rien')
        texte = '\n'.join(lignes)
        for clair in [*clairs, INCONNU['flux']]:
            self.assertNotIn(clair, texte)
            self.assertNotIn(_empreinte(clair), texte)

    def test_un_500_du_flux_ne_journalise_pas_le_chemin(self):
        _jeton, clair = fabriques.jeton(self.u1, 'flux')
        with mock.patch.object(FluxVue, 'get', side_effect=RuntimeError('panne')), journaux() as lignes:
            reponse = APIClient().get(f'{PREFIXE}flux/{clair}.ics')
        self.assertEqual(reponse.status_code, 500)
        self.assertEqual(reponse['Cache-Control'], 'no-store')
        texte = '\n'.join(lignes)
        self.assertIn('flux/<masqué>.ics', texte)
        self.assertNotIn(clair, texte)
        self.assertNotIn(clair, reponse.content.decode())

    def test_debit_par_jeton_429(self):
        _jeton, clair = fabriques.jeton(self.u1, 'tuile')
        _autre, clair_autre = fabriques.jeton(self.u2, 'tuile')
        porteur = self._porteur(clair)
        with mock.patch.object(ThrottleTuile, 'rate', '2/hour'):
            for _ in range(2):
                self._porteur(INCONNU['tuile']).get(PREFIXE + 'tuile/')  # un refus ne compte pas
                self.assertNotEqual(porteur.get(PREFIXE + 'tuile/').status_code, 429)
            refus = porteur.get(PREFIXE + 'tuile/')
            self.assertEqual(refus.status_code, 429)
            self.assertIn('detail', refus.json())
            self.assertNotEqual(self._porteur(clair_autre).get(PREFIXE + 'tuile/').status_code, 429)


class SortiesObservabiliteTests(_Base):
    """Le jeton du flux est DANS l'adresse (imposé par Apple) : aucune sortie d'observabilité ne le
    porte (journal JSON, journal d'accès, requêtes lentes, pile d'exception, Sentry), toutes gardent
    le chemin masqué pour diagnostiquer ; l'en-tête `Authorization` de la capture et de la tuile n'est
    écrit nulle part."""

    def setUp(self):
        super().setUp()
        _jf, self.flux = fabriques.jeton(self.u1, 'flux')
        _jc, self.capture = fabriques.jeton(self.u1, 'capture')
        _jt, self.tuile = fabriques.jeton(self.u1, 'tuile')
        revoque, self.revoque = fabriques.jeton(self.u2, 'flux')
        JetonAcces.objects.filter(pk=revoque.pk).update(revoque_le=T0)
        self.clairs = [self.flux, self.capture, self.tuile, self.revoque]
        self.adresse = f'{PREFIXE}flux/{self.flux}.ics'
        self.masquee = f'{PREFIXE}flux/<masqué>.ics'

    def _sans_aucun_clair(self, texte):
        for clair in self.clairs:
            self.assertNotIn(clair, texte)
            self.assertNotIn(clair[4:], texte)
            self.assertNotIn(_empreinte(clair), texte)

    def test_journal_json_sans_jeton_avec_le_chemin_masque(self):
        panne = RuntimeError(f'panne de {self.adresse}')
        with override_settings(REQUEST_ACCESS_LOG=True, SLOW_REQUEST_MS=1), journal_json() as sortie:
            self.assertEqual(APIClient().get(self.adresse).status_code, 200)
            self.assertEqual(APIClient().get(f'{PREFIXE}flux/{self.revoque}.ics').status_code, 404)
            self.assertEqual(APIClient().get(f'{PREFIXE}flux/{self.flux}').status_code, 404)
            with mock.patch('apps.taches.views.presence._corps_flux', side_effect=panne):
                reponse = APIClient().get(self.adresse, HTTP_REFERER=f'https://ex.ma{self.adresse}')
            self.assertEqual(reponse.status_code, 500)
            self.assertEqual(self._porteur(self.capture).post(
                PREFIXE + 'capture/', {'titre': 'Note'}, format='json').status_code, 201)
            self.assertEqual(self._porteur(self.tuile).get(PREFIXE + 'tuile/').status_code, 200)
        texte = sortie.getvalue()
        self._sans_aucun_clair(texte)
        lignes = [json.loads(ligne) for ligne in texte.splitlines()]
        self.assertIn(f'GET {self.masquee} -> 200', [ligne['message'] for ligne in lignes])
        refus = [ligne for ligne in lignes if ligne['message'] == 'taches : jeton flux refusé']
        self.assertEqual([ligne.get('path') for ligne in refus], [self.masquee])
        self.assertTrue(any(ligne['message'].startswith('Requête lente') and self.masquee in ligne['message']
                            for ligne in lignes))
        self.assertTrue(any(f'panne de {self.masquee}' in ligne.get('exc', '') for ligne in lignes))
        self.assertIn(f'{PREFIXE}capture/', [ligne.get('path') for ligne in lignes])

    def test_sentry_sans_jeton_avec_le_chemin_masque(self):
        panne = RuntimeError(f'panne de {self.adresse}')
        with override_settings(SLOW_REQUEST_MS=1), sentry_capture() as charges:
            self.assertEqual(appel_wsgi(self.adresse), 200)
            self.assertEqual(appel_wsgi(f'{PREFIXE}flux/{self.revoque}.ics'), 404)
            with mock.patch('apps.taches.views.presence._corps_flux', side_effect=panne):
                self.assertEqual(appel_wsgi(self.adresse, HTTP_REFERER=f'https://ex.ma{self.adresse}'), 500)
            self.assertEqual(appel_wsgi(PREFIXE + 'tuile/', HTTP_AUTHORIZATION=f'Bearer {self.tuile}'), 200)
            self.assertEqual(appel_wsgi(PREFIXE + 'capture/', 'post', data=json.dumps({'titre': 'Note'}),
                                        content_type='application/json',
                                        HTTP_AUTHORIZATION=f'Bearer {self.capture}'), 201)
        self.assertTrue(charges, 'le transport de test ne reçoit rien')
        self._sans_aucun_clair(json.dumps(charges, default=str))
        types = {charge.get('type', 'event') for charge in charges}
        self.assertTrue({'transaction', 'event'} <= types, types)
        adresses = {(charge.get('request') or {}).get('url') for charge in charges}
        self.assertIn(f'http://testserver{self.masquee}', adresses)
        erreurs = [charge for charge in charges if charge.get('type', 'event') == 'event' and 'exception' in charge]
        self.assertTrue(any(f'panne de {self.masquee}' in json.dumps(charge, ensure_ascii=False) for charge in erreurs))
