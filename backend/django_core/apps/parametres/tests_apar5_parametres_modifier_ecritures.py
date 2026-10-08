"""APAR5 — TOUTE écriture de réglages société exige ``parametres_modifier``.

Constat C-APAR-003 : ASEC31 avait posé le couple
``[IsAdminOrResponsableTier, HasPermissionOrLegacy('parametres_modifier')]``
sur le profil, les téléversements, les tarifs et les textes de documents,
mais messages client, modèles d'e-mail, statuts, approbations, taux de TVA,
conditions de paiement, unités, cadence de relance et réalisations restaient
ouverts au seul PALIER : Admin RH, Technicien responsable et Commercial
responsable (palier « responsable » via ``users_voir``) y écrivaient.

Le test PARCOURT ``apps/parametres/urls.py`` (toutes les méthodes d'écriture
de toutes les routes) : une vue d'écriture ajoutée demain sans le droit est
NOMMÉE dans l'échec. Exemptions NOMMÉES ci-dessous.

Test-du-test : retirer ``HasPermissionOrLegacy`` d'une seule vue ⇒ le test
nomme cette route et échoue.
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import URLPattern, URLResolver
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres import urls as parametres_urls
from apps.parametres.models_messages import MessageTemplate
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ADMIN_RH_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS, DIRECTEUR_PERMISSIONS,
    TECHNICIEN_RESP_PERMISSIONS,
)
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/parametres/'
ECRITURES = ('post', 'put', 'patch', 'delete')

#: Routes d'écriture HORS du droit ``parametres_modifier``, chacune motivée.
EXEMPTIONS = {
    # Droit DÉDIÉ `localisation_gerer` (RESPONSABLE_PERMISSIONS le porte
    # délibérément) — alignement = décision fondateur non posée (APAR5).
    'traductions/': 'localisation_gerer',
    'fetes-mobiles/enregistrer/': 'localisation_gerer',
    'onboarding-localisation/': 'localisation_gerer',
    # Calcul de ROI à la volée : aucune écriture en base.
    'tarification/roi/': 'calcul sans écriture',
}

#: Routes d'APAR5 sur lesquelles le Directeur doit RÉUSSIR (jamais 403).
ROUTES_APAR5 = (
    'messages/', 'email-templates/', 'statuts/', 'approbations/',
    'taux-tva/', 'conditions-paiement/', 'unites-mesure/',
    'cadence-relance/', 'realisations/',
)

NON_HABILITES = {
    'Admin RH': ADMIN_RH_PERMISSIONS,
    'Technicien responsable': TECHNICIEN_RESP_PERMISSIONS,
    'Commercial responsable': COMMERCIAL_RESP_PERMISSIONS,
}

_GROUPE = re.compile(r'\(\?P<[^>]+>[^)]*\)')


def _chemin(regex_ou_route):
    """Chemin concret d'un motif d'URL (paramètres remplacés par 999999)."""
    s = str(regex_ou_route)
    s = _GROUPE.sub('999999', s)
    s = re.sub(r'<[^>]+>', '999999', s)
    return s.lstrip('^').rstrip('$').replace('\\', '')


def _routes_ecriture(patterns=None, prefixe=''):
    """[(méthode, chemin)] de toutes les écritures déclarées par l'urlconf."""
    out = []
    for p in (parametres_urls.urlpatterns if patterns is None else patterns):
        if isinstance(p, URLResolver):
            out += _routes_ecriture(
                p.url_patterns, prefixe + _chemin(p.pattern))
            continue
        if not isinstance(p, URLPattern):  # pragma: no cover
            continue
        route = prefixe + _chemin(p.pattern)
        if 'format' in str(p.pattern) or '.999999' in route:
            continue  # suffixes de format du routeur
        cb = p.callback
        cls = getattr(cb, 'cls', None)
        if cls is not None and cls.__name__ == 'APIRootView':
            continue  # racine navigable des routeurs (lecture)
        permises = set(getattr(cls, 'http_method_names', []) or [])
        actions = getattr(cb, 'actions', None)
        methodes = (set(actions) if actions is not None else permises)
        for m in sorted(methodes & set(ECRITURES) & (permises or methodes)):
            out.append((m, route))
    return out


def _exemptee(route):
    return any(route.startswith(prefixe) for prefixe in EXEMPTIONS)


class EcrituresReglagesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR5 Co', slug='apar5-co')
        self.users = {}
        roles = dict(NON_HABILITES, Directeur=DIRECTEUR_PERMISSIONS)
        for i, (nom, perms) in enumerate(roles.items()):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms),
                est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'apar5_u{i}', password='x', role=role,
                company=self.company)

    def _api(self, nom):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(
            self.users[nom]))
        return api

    def test_registre(self):
        self.assertIn('parametres_modifier', DIRECTEUR_PERMISSIONS)
        for nom, perms in NON_HABILITES.items():
            self.assertNotIn('parametres_modifier', perms, nom)

    def test_routes_apar5_sont_parcourues(self):
        routes = {r for _m, r in _routes_ecriture()}
        for prefixe in ROUTES_APAR5:
            self.assertTrue(any(r.startswith(prefixe) for r in routes),
                            f'route non trouvée dans urls.py : {prefixe}')

    def test_toute_ecriture_exige_parametres_modifier(self):
        ouvertes = []
        for methode, route in _routes_ecriture():
            if _exemptee(route):
                continue
            for nom in NON_HABILITES:
                r = getattr(self._api(nom), methode)(
                    BASE + route, {}, format='json')
                if r.status_code != 403:
                    ouvertes.append(f'{methode.upper()} {route} ({nom}) → '
                                    f'{r.status_code}')
        self.assertEqual(ouvertes, [], 'écritures ouvertes sans le droit')

    def test_le_directeur_n_est_jamais_refuse(self):
        refusees = []
        for methode, route in _routes_ecriture():
            if not route.startswith(ROUTES_APAR5):
                continue
            r = getattr(self._api('Directeur'), methode)(
                BASE + route, {}, format='json')
            if r.status_code == 403:
                refusees.append(f'{methode.upper()} {route}')
        self.assertEqual(refusees, [])

    def test_message_client_inchange_apres_refus(self):
        for nom in NON_HABILITES:
            r = self._api(nom).put(f'{BASE}messages/', {
                'cle': 'facture', 'corps_fr': 'Piraté {lien}'}, format='json')
            self.assertEqual(r.status_code, 403, nom)
        self.assertFalse(MessageTemplate.objects.filter(
            company=self.company, corps_fr__contains='Piraté').exists())
        ok = self._api('Directeur').put(f'{BASE}messages/', {
            'cle': 'facture', 'corps_fr': 'Bonjour {lien}'}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
