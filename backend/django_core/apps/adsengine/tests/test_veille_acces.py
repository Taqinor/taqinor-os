"""VEIL12 — Accès Ad Library du pilote de veille, séparé des campagnes TAQINOR.

Prouve : jeton absent / interrupteur faux / société hors liste → AUCUNE requête
réseau (transport qui échoue s'il est appelé) ; les jetons de campagne et une
MetaConnection remplie ne servent JAMAIS ; le jeton et le secret d'application
n'apparaissent dans aucun log, aucune réponse d'API, aucun message d'erreur ;
aucun module ``veille_*``/``ad_library_client`` n'importe le client de campagne
ni la connexion de campagne.
"""
import ast
import datetime
import json
import logging
import pathlib
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import veille_acces
from apps.adsengine.models import MetaConnection

User = get_user_model()

JETON = 'EAAVEILLEJETONSECRET1234567890'
SECRET = 'appsecretveille0987654321'
APP_ID = '424242'

APP_DIR = pathlib.Path(__file__).resolve().parents[1]


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _transport_interdit(*args, **kwargs):
    raise AssertionError('Aucune requête réseau ne doit partir ici.')


def _client_interdit():
    import httpx
    return httpx.Client(transport=httpx.MockTransport(_transport_interdit))


class EtatSansAppelTests(TestCase):
    def setUp(self):
        cache.delete(veille_acces.CLE_CACHE_VERIFICATION)
        self.company = Company.objects.create(nom='YanBow', slug='yanbow-acc')

    @override_settings(META_AD_LIBRARY_ACCESS_TOKEN='',
                       META_AD_LIBRARY_ENABLED=True)
    def test_jeton_absent_non_configure_zero_appel(self):
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            resultat = veille_acces.verifier(
                self.company, http_client=_client_interdit())
        self.assertEqual(resultat, {'etat': 'non_configure',
                                    'expire_le': None})

    @override_settings(META_AD_LIBRARY_ACCESS_TOKEN=JETON,
                       META_AD_LIBRARY_ENABLED=False)
    def test_interrupteur_faux_desactive_zero_appel(self):
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            resultat = veille_acces.verifier(
                self.company, http_client=_client_interdit())
        self.assertEqual(resultat['etat'], 'desactive')

    @override_settings(META_AD_LIBRARY_ACCESS_TOKEN='',
                       META_AD_LIBRARY_ENABLED=True,
                       META_SYSTEM_USER_TOKEN='EAACAMPAGNETAQINOR',
                       META_LEAD_ADS_ACCESS_TOKEN='EAALEADADSTAQINOR')
    def test_jetons_de_campagne_et_metaconnection_jamais_utilises(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True, ad_account_id='act_1',
            credentials={'access_token': 'EAAMETACONNECTION'})
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            with mock.patch('httpx.Client.send',
                            side_effect=_transport_interdit):
                resultat = veille_acces.verifier(self.company)
            self.assertEqual(resultat['etat'], 'non_configure')
            with self.assertRaises(veille_acces.AccesRefuse) as ctx:
                veille_acces.exiger_utilisable(self.company)
        self.assertEqual(ctx.exception.etat, 'non_configure')

    @override_settings(META_AD_LIBRARY_ACCESS_TOKEN=JETON,
                       META_AD_LIBRARY_ENABLED=True,
                       VEILLE_SOCIETES_AUTORISEES=[])
    def test_liste_vide_personne_n_est_autorise(self):
        resultat = veille_acces.verifier(
            self.company, http_client=_client_interdit())
        self.assertEqual(resultat['etat'], 'non_autorise')

    @override_settings(META_AD_LIBRARY_ACCESS_TOKEN=JETON,
                       META_AD_LIBRARY_ENABLED=True)
    def test_societe_hors_liste_meme_gestionnaire_zero_appel_api(self):
        autre = Company.objects.create(nom='Autre', slug='autre-acc')
        user = make_user(autre, 'gest_hors_liste',
                         ['adsengine_view', 'adsengine_manage'])
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            with mock.patch('httpx.Client.send',
                            side_effect=_transport_interdit):
                resp = auth(user).get(
                    '/api/django/adsengine/veille/couverture/?verifier=1')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['acces']['etat'], 'non_autorise')


class EtatAvecVerificationTests(TestCase):
    def setUp(self):
        cache.delete(veille_acces.CLE_CACHE_VERIFICATION)
        self.company = Company.objects.create(nom='YanBow', slug='yanbow-ver')
        self.now = timezone.make_aware(datetime.datetime(2026, 10, 5, 9, 0))

    def _etat(self, verification):
        with override_settings(
                META_AD_LIBRARY_ACCESS_TOKEN=JETON,
                META_AD_LIBRARY_ENABLED=True,
                VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            return veille_acces.etat(
                self.company, verification=verification, now=self.now)

    def test_pret_sans_verification(self):
        self.assertEqual(self._etat({}), {'etat': 'pret', 'expire_le': None})

    def test_expire_bientot_a_j_moins_10(self):
        res = self._etat({'valide': True,
                          'expire_le': '2026-10-14T09:00:00+00:00'})
        self.assertEqual(res['etat'], 'expire_bientot')
        self.assertEqual(res['expire_le'], '2026-10-14T09:00:00+00:00')

    def test_pret_au_dela_de_10_jours(self):
        res = self._etat({'valide': True,
                          'expire_le': '2026-12-01T00:00:00+00:00'})
        self.assertEqual(res['etat'], 'pret')

    def test_invalide(self):
        res = self._etat({'valide': False, 'expire_le': None})
        self.assertEqual(res['etat'], 'invalide')


@override_settings(META_AD_LIBRARY_ACCESS_TOKEN=JETON,
                   META_AD_LIBRARY_APP_ID=APP_ID,
                   META_AD_LIBRARY_APP_SECRET=SECRET,
                   META_AD_LIBRARY_ENABLED=True)
class MasquageTests(TestCase):
    """Trois preuves de masquage : logs, réponse d'API, message d'erreur."""

    def setUp(self):
        cache.delete(veille_acces.CLE_CACHE_VERIFICATION)
        self.company = Company.objects.create(nom='YanBow', slug='yanbow-mask')

    def test_secret_masque_comme_le_jeton(self):
        publique = veille_acces.config_publique()
        self.assertEqual(publique['jeton'], veille_acces.MASQUE)
        self.assertEqual(publique['app_secret'], veille_acces.MASQUE)
        texte = repr(veille_acces.configuration())
        self.assertNotIn(JETON, texte)
        self.assertNotIn(SECRET, texte)

    def test_masquage_logs(self):
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            with self.assertLogs('apps.adsengine', level=logging.DEBUG) as cm:
                veille_acces.etat(self.company)
                veille_acces.etat(Company.objects.create(
                    nom='Hors', slug='hors-mask'))
        sortie = '\n'.join(cm.output)
        self.assertNotIn(JETON, sortie)
        self.assertNotIn(SECRET, sortie)

    def test_masquage_reponse_api(self):
        user = make_user(self.company, 'mask_api',
                         ['adsengine_view', 'adsengine_manage'])
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            resp = auth(user).get('/api/django/adsengine/veille/couverture/')
        self.assertEqual(resp.status_code, 200)
        contenu = resp.content.decode('utf-8')
        self.assertNotIn(JETON, contenu)
        self.assertNotIn(SECRET, contenu)
        self.assertEqual(resp.data['acces']['etat'], 'pret')

    def test_masquage_message_erreur(self):
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[]):
            with self.assertRaises(veille_acces.AccesRefuse) as ctx:
                veille_acces.exiger_utilisable(self.company)
        self.assertNotIn(JETON, str(ctx.exception))
        self.assertNotIn(SECRET, ctx.exception.message_fr)
        brut = f'erreur Meta token={JETON} app={APP_ID}|{SECRET}'
        nettoye = veille_acces.masquer_secrets(brut)
        self.assertNotIn(JETON, nettoye)
        self.assertNotIn(SECRET, nettoye)


class IsolationStatiqueTests(TestCase):
    """Aucun module de la veille n'importe le client de campagne, la connexion
    de campagne, ni ne lit les variables de jetons de campagne."""

    INTERDITS_NOMS = {'MetaConnection', 'meta_client'}
    INTERDITS_TEXTES = ('META_SYSTEM_USER_TOKEN', 'META_LEAD_ADS_')

    def _modules(self):
        fichiers = sorted(APP_DIR.glob('veille_*.py'))
        client = APP_DIR / 'ad_library_client.py'
        if client.exists():
            fichiers.append(client)
        return fichiers

    def test_aucun_import_ni_lecture_interdite(self):
        fichiers = self._modules()
        self.assertTrue(fichiers)
        for chemin in fichiers:
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            docstrings = {
                id(n.value) for n in ast.walk(arbre)
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
            }
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.ImportFrom):
                    noms = [noeud.module or ''] + [a.name for a in noeud.names]
                elif isinstance(noeud, ast.Import):
                    noms = [a.name for a in noeud.names]
                elif isinstance(noeud, ast.Name):
                    noms = [noeud.id]
                elif isinstance(noeud, ast.Attribute):
                    noms = [noeud.attr]
                elif (isinstance(noeud, ast.Constant)
                      and isinstance(noeud.value, str)
                      and id(noeud) not in docstrings):
                    for interdit in self.INTERDITS_TEXTES:
                        self.assertNotIn(interdit, noeud.value,
                                         f'{chemin.name} lit {interdit}')
                    continue
                else:
                    continue
                for nom in noms:
                    for interdit in self.INTERDITS_NOMS:
                        self.assertNotIn(interdit, nom.split('.'),
                                         f'{chemin.name} importe {interdit}')
                    for interdit in self.INTERDITS_TEXTES:
                        self.assertFalse(nom.startswith(interdit),
                                         f'{chemin.name} lit {nom}')

    def test_couverture_json_sans_secret(self):
        texte = json.dumps(veille_acces.config_publique())
        self.assertNotIn(JETON, texte)
