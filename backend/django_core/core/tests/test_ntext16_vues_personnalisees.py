"""NTEXT16 — vues de liste personnalisées, partageables par équipe.

Couvre : le CRUD scopé société (``company``/``owner`` posés côté serveur,
jamais lus du corps), le filtre ``?cible=``, les trois portées de partage et —
le critère — le fait qu'une vue ``equipe`` soit visible d'un COÉQUIPIER et
INVISIBLE d'un collègue hors équipe, via le fournisseur d'appartenance
enregistrable (``core.vues.register_equipe_membres_provider``).

Découplage : le test enregistre son fournisseur d'équipe sur un modèle de
FONDATION — aucun import d'app domaine (``core`` reste couche de base).
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core import vues as vues_mod
from core.models import VuePersonnalisee

User = get_user_model()

URL = '/api/django/core/vues/'

_seq = itertools.count(1)

# Appartenance d'équipe DE TEST : {user_id: [equipe_id, …]}.
_EQUIPES = {}


def _provider_de_test(user):
    return _EQUIPES.get(user.pk, [])


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT16 Co {next(_seq)}')


def make_user(company, username=None):
    return User.objects.create_user(
        username=username or f'ntext16-u{next(_seq)}', password='x',
        role_legacy='normal', company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _ids(response):
    donnees = response.data
    resultats = donnees['results'] if 'results' in donnees else donnees
    return {r['id'] for r in resultats}


class CrudScopingTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT16 CRUD')
        self.autre = make_company('NTEXT16 CRUD Autre')
        self.user = make_user(self.company, 'ntext16-crud')
        self.api = _auth(self.user)

    def test_create_forces_company_and_owner_server_side(self):
        res = self.api.post(URL, {
            'cible': 'crm.lead', 'nom': 'Mes leads chauds',
            'config': {'filters': {'priorite': 'haute'}, 'tri': ['-created_at']},
            'company': self.autre.id,   # doit être IGNORÉ
            'owner': 999,               # doit être IGNORÉ
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        vue = VuePersonnalisee.objects.get(id=res.data['id'])
        self.assertEqual(vue.company, self.company)
        self.assertEqual(vue.owner, self.user)
        self.assertEqual(vue.partage, VuePersonnalisee.Partage.PRIVE)
        self.assertEqual(vue.config['filters'], {'priorite': 'haute'})

    def test_team_share_requires_a_team(self):
        res = self.api.post(URL, {
            'cible': 'crm.lead', 'nom': 'Sans équipe', 'partage': 'equipe',
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('equipe', res.data)

    def test_view_of_another_company_is_never_reachable(self):
        etrangere = VuePersonnalisee.objects.create(
            company=self.autre, cible='crm.lead', nom='Étrangère',
            partage=VuePersonnalisee.Partage.SOCIETE)
        self.assertNotIn(etrangere.id, _ids(self.api.get(URL)))
        self.assertEqual(
            self.api.get(f'{URL}{etrangere.id}/').status_code, 404)

    def test_cible_filter(self):
        leads = VuePersonnalisee.objects.create(
            company=self.company, owner=self.user, cible='crm.lead',
            nom='Leads')
        devis = VuePersonnalisee.objects.create(
            company=self.company, owner=self.user, cible='ventes.devis',
            nom='Devis')
        self.assertEqual(_ids(self.api.get(f'{URL}?cible=crm.lead')),
                         {leads.id})
        self.assertEqual(_ids(self.api.get(f'{URL}?cible=ventes.devis')),
                         {devis.id})


class PartageTests(TestCase):
    """Le critère NTEXT16 : le coéquipier voit, l'autre non."""

    def setUp(self):
        self.company = make_company('NTEXT16 Partage')
        self.commercial = make_user(self.company, 'ntext16-commercial')
        self.coequipier = make_user(self.company, 'ntext16-coequipier')
        self.hors_equipe = make_user(self.company, 'ntext16-hors-equipe')

        _EQUIPES.clear()
        _EQUIPES[self.commercial.pk] = ['equipe-nord']
        _EQUIPES[self.coequipier.pk] = ['equipe-nord']
        _EQUIPES[self.hors_equipe.pk] = ['equipe-sud']
        vues_mod.register_equipe_membres_provider(_provider_de_test)
        self.addCleanup(_EQUIPES.clear)
        self.addCleanup(
            lambda: _provider_de_test in vues_mod._EQUIPE_PROVIDERS
            and vues_mod._EQUIPE_PROVIDERS.remove(_provider_de_test))

    def _vue(self, partage, equipe='', nom='Mes leads chauds'):
        return VuePersonnalisee.objects.create(
            company=self.company, owner=self.commercial, cible='crm.lead',
            nom=nom, partage=partage, equipe=equipe)

    def test_team_view_is_visible_to_a_teammate_only(self):
        vue = self._vue(VuePersonnalisee.Partage.EQUIPE, 'equipe-nord')

        self.assertIn(vue.id, _ids(_auth(self.commercial).get(URL)))
        self.assertIn(vue.id, _ids(_auth(self.coequipier).get(URL)))
        self.assertNotIn(vue.id, _ids(_auth(self.hors_equipe).get(URL)))

        self.assertEqual(
            _auth(self.coequipier).get(f'{URL}{vue.id}/').status_code, 200)
        self.assertEqual(
            _auth(self.hors_equipe).get(f'{URL}{vue.id}/').status_code, 404)

    def test_private_view_is_visible_to_its_owner_only(self):
        vue = self._vue(VuePersonnalisee.Partage.PRIVE)
        self.assertIn(vue.id, _ids(_auth(self.commercial).get(URL)))
        self.assertNotIn(vue.id, _ids(_auth(self.coequipier).get(URL)))
        self.assertNotIn(vue.id, _ids(_auth(self.hors_equipe).get(URL)))

    def test_company_view_is_visible_to_everyone_in_the_company(self):
        vue = self._vue(VuePersonnalisee.Partage.SOCIETE)
        for user in (self.commercial, self.coequipier, self.hors_equipe):
            self.assertIn(vue.id, _ids(_auth(user).get(URL)))

    def test_a_team_view_never_crosses_the_tenant_boundary(self):
        """Même équipe homonyme dans une AUTRE société : jamais visible."""
        autre_company = make_company('NTEXT16 Partage Autre')
        voisin = make_user(autre_company, 'ntext16-voisin')
        _EQUIPES[voisin.pk] = ['equipe-nord']
        vue = self._vue(VuePersonnalisee.Partage.EQUIPE, 'equipe-nord')
        self.assertNotIn(vue.id, _ids(_auth(voisin).get(URL)))


class FournisseurEquipeTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT16 Fournisseur')
        self.user = make_user(self.company, 'ntext16-fournisseur')

    def test_without_provider_a_team_view_is_owner_only(self):
        """Défaut SÛR : sans fournisseur enregistré, on ne montre pas plus."""
        autre = make_user(self.company, 'ntext16-fournisseur-autre')
        vue = VuePersonnalisee.objects.create(
            company=self.company, owner=self.user, cible='crm.lead',
            nom='Équipe sans résolveur',
            partage=VuePersonnalisee.Partage.EQUIPE, equipe='inconnue')
        originaux = list(vues_mod._EQUIPE_PROVIDERS)
        vues_mod._EQUIPE_PROVIDERS.clear()
        try:
            self.assertIn(vue.id, _ids(_auth(self.user).get(URL)))
            self.assertNotIn(vue.id, _ids(_auth(autre).get(URL)))
        finally:
            vues_mod._EQUIPE_PROVIDERS[:] = originaux

    def test_register_requires_a_callable(self):
        with self.assertRaises(ValueError):
            vues_mod.register_equipe_membres_provider(None)

    def test_a_failing_provider_is_isolated(self):
        def _casse(user):
            raise RuntimeError('boom')

        vues_mod.register_equipe_membres_provider(_casse)
        try:
            self.assertEqual(vues_mod.equipes_de(self.user), set())
        finally:
            vues_mod._EQUIPE_PROVIDERS.remove(_casse)

    def test_anonymous_or_unsaved_user_has_no_team(self):
        self.assertEqual(vues_mod.equipes_de(None), set())
        self.assertEqual(vues_mod.equipes_de(User()), set())
