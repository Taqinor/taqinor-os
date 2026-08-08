"""VAO12 — matrice de permissions + isolation multi-société.

Le partage choisi, et pourquoi :
  * ``veille_ao_voir``  — LARGE. Un commercial doit voir passer les avis,
    sinon la veille ne sert à personne. Ce sont des avis de marché PUBLICS.
  * ``veille_ao_gerer`` — palier Responsable/Directeur. Régler les mots-clés,
    les sources et les règles décide de ce que TOUTE la société voit.

Un technicien n'a ni l'un ni l'autre : aucun accès n'est ÉLARGI par rapport à
aujourd'hui, le module est neuf et n'ouvre que ses propres routes.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import (
    COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS, RESPONSABLE_PERMISSIONS,
    TECHNICIEN_PERMISSIONS, ALL_PERMISSIONS, Role,
)
from apps.veille_ao.models import SourceVeille, TypeSource
from apps.veille_ao.viewsets import (
    AvisMarcheViewSet, MotCleVeilleViewSet, RegleExclusionViewSet,
    SourceVeilleViewSet,
)
from authentication.models import Company, CustomUser
from core.viewsets import CompanyScopedModelViewSet

BASE = '/api/django/veille_ao/'
PREFIXES = ('sources', 'avis', 'mots-cles', 'regles-exclusion')

VEILLE_AO_VOIR = 'veille_ao_voir'
VEILLE_AO_GERER = 'veille_ao_gerer'


class CodesDeclaresTests(TestCase):
    def test_les_deux_codes_sont_au_catalogue(self):
        self.assertIn(VEILLE_AO_VOIR, ALL_PERMISSIONS)
        self.assertIn(VEILLE_AO_GERER, ALL_PERMISSIONS)

    def test_lecture_mappee_largement(self):
        """Un commercial doit voir les avis — c'est le but du module."""
        self.assertIn(VEILLE_AO_VOIR, COMMERCIAL_PERMISSIONS)
        self.assertIn(VEILLE_AO_VOIR, RESPONSABLE_PERMISSIONS)
        self.assertIn(VEILLE_AO_VOIR, DIRECTEUR_PERMISSIONS)

    def test_gestion_reservee_au_palier_responsable(self):
        self.assertIn(VEILLE_AO_GERER, RESPONSABLE_PERMISSIONS)
        self.assertIn(VEILLE_AO_GERER, DIRECTEUR_PERMISSIONS)
        self.assertNotIn(VEILLE_AO_GERER, COMMERCIAL_PERMISSIONS)

    def test_un_technicien_n_a_aucun_acces(self):
        """Aucun accès élargi : le module est neuf, il n'ouvre que ses
        propres routes."""
        self.assertNotIn(VEILLE_AO_VOIR, TECHNICIEN_PERMISSIONS)
        self.assertNotIn(VEILLE_AO_GERER, TECHNICIEN_PERMISSIONS)


class SocleDesViewsetsTests(TestCase):
    """``check_platform.py`` refuse tout NOUVEAU ModelViewSet hors socle."""

    VUES = (SourceVeilleViewSet, AvisMarcheViewSet, MotCleVeilleViewSet,
            RegleExclusionViewSet)

    def test_toutes_les_vues_sont_sur_le_socle_scope_societe(self):
        for vue in self.VUES:
            self.assertTrue(
                issubclass(vue, CompanyScopedModelViewSet), vue.__name__)

    def test_toutes_les_vues_declarent_lecture_et_ecriture(self):
        for vue in self.VUES:
            self.assertEqual(vue.read_permission, VEILLE_AO_VOIR,
                             vue.__name__)
            self.assertEqual(vue.write_permission, VEILLE_AO_GERER,
                             vue.__name__)


class BaseMatrice(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Permissions')

    def _api(self, permissions, suffixe):
        role = Role.objects.create(
            company=self.company, nom=f'Rôle {suffixe}',
            permissions=list(permissions))
        user = CustomUser.objects.create_user(
            username=f'vao_{suffixe}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api


class MatriceDeLectureTests(BaseMatrice):
    def test_commercial_lit_toutes_les_routes(self):
        api = self._api(COMMERCIAL_PERMISSIONS, 'commercial')
        for prefixe in PREFIXES:
            self.assertEqual(
                api.get(f'{BASE}{prefixe}/').status_code, 200, prefixe)

    def test_responsable_lit_toutes_les_routes(self):
        api = self._api(RESPONSABLE_PERMISSIONS, 'responsable')
        for prefixe in PREFIXES:
            self.assertEqual(
                api.get(f'{BASE}{prefixe}/').status_code, 200, prefixe)

    def test_directeur_lit_toutes_les_routes(self):
        api = self._api(DIRECTEUR_PERMISSIONS, 'directeur')
        for prefixe in PREFIXES:
            self.assertEqual(
                api.get(f'{BASE}{prefixe}/').status_code, 200, prefixe)

    def test_technicien_est_refuse_partout(self):
        api = self._api(TECHNICIEN_PERMISSIONS, 'technicien')
        for prefixe in PREFIXES:
            self.assertEqual(
                api.get(f'{BASE}{prefixe}/').status_code, 403, prefixe)

    def test_anonyme_refuse(self):
        anonyme = APIClient()
        for prefixe in PREFIXES:
            self.assertIn(
                anonyme.get(f'{BASE}{prefixe}/').status_code, (401, 403),
                prefixe)


class MatriceDEcritureTests(BaseMatrice):
    CORPS = {
        'sources': {'code': 'test-src', 'libelle': 'Source de test'},
        'mots-cles': {'libelle': 'test-mot'},
        'regles-exclusion': {'portee': 'acheteur', 'valeur': 'X',
                             'motif': 'Test'},
    }

    def test_commercial_ne_peut_pas_ecrire(self):
        """Lire oui, RÉGLER non : les mots-clés et les sources décident de ce
        que toute la société voit."""
        api = self._api(COMMERCIAL_PERMISSIONS, 'commercial_w')
        for prefixe, corps in self.CORPS.items():
            self.assertEqual(
                api.post(f'{BASE}{prefixe}/', corps,
                         format='json').status_code, 403, prefixe)

    def test_technicien_ne_peut_pas_ecrire(self):
        api = self._api(TECHNICIEN_PERMISSIONS, 'technicien_w')
        for prefixe, corps in self.CORPS.items():
            self.assertEqual(
                api.post(f'{BASE}{prefixe}/', corps,
                         format='json').status_code, 403, prefixe)

    def test_responsable_peut_ecrire(self):
        api = self._api(RESPONSABLE_PERMISSIONS, 'responsable_w')
        reponse = api.post(f'{BASE}mots-cles/', {'libelle': 'ombriere'},
                           format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def test_directeur_peut_ecrire(self):
        api = self._api(DIRECTEUR_PERMISSIONS, 'directeur_w')
        reponse = api.post(f'{BASE}regles-exclusion/',
                           {'portee': 'acheteur', 'valeur': 'Hors sujet',
                            'motif': 'Acheteur sans besoin solaire'},
                           format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)


class SocieteForceeCoteServeurTests(BaseMatrice):
    def test_company_n_est_jamais_lue_du_corps_de_la_requete(self):
        """ARC2 — même en la POSTant explicitement, elle est ignorée."""
        autre = Company.objects.create(nom='Société volée')
        api = self._api(RESPONSABLE_PERMISSIONS, 'forcee')
        reponse = api.post(
            f'{BASE}mots-cles/',
            {'libelle': 'tentative', 'company': autre.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        from apps.veille_ao.models import MotCleVeille
        mot = MotCleVeille.objects.get(libelle='tentative')
        self.assertEqual(mot.company_id, self.company.pk)


class IsolationMultiTenantTests(BaseMatrice):
    def test_une_societe_ne_voit_jamais_les_sources_d_une_autre(self):
        autre = Company.objects.create(nom='Autre Permissions')
        SourceVeille.objects.create(
            company=autre, code='voisine', libelle='Source du voisin',
            type_source=TypeSource.PORTAIL_OFFICIEL, actif=True)
        SourceVeille.objects.create(
            company=self.company, code='mienne', libelle='Ma source',
            type_source=TypeSource.SAISIE_MANUELLE, actif=True)

        api = self._api(RESPONSABLE_PERMISSIONS, 'isolation')
        reponse = api.get(f'{BASE}sources/')

        self.assertEqual(reponse.status_code, 200)
        codes = {ligne['code'] for ligne in reponse.data['results']}
        self.assertEqual(codes, {'mienne'})

    def test_une_source_d_une_autre_societe_est_introuvable(self):
        autre = Company.objects.create(nom='Autre Permissions 2')
        source = SourceVeille.objects.create(
            company=autre, code='voisine', libelle='Source du voisin',
            type_source=TypeSource.PORTAIL_OFFICIEL, actif=True)
        api = self._api(RESPONSABLE_PERMISSIONS, 'isolation_detail')
        self.assertEqual(
            api.get(f'{BASE}sources/{source.pk}/').status_code, 404)
