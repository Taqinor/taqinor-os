"""VAO13 — le manifeste plateforme ne déclare QUE ce qui est câblé.

``core/platform_coverage.py`` (règle d'honnêteté ARC41) fait rougir la CI sur
toute surface déclarée non câblée, ET sur toute incohérence entre les deux
surfaces qui partagent l'espace de clés ``'app.model'`` : un modèle
chatter-isé doit être cherchable, et réciproquement.

Ce module vérifie les trois choses que VAO13 promet :
  1. le chatter ``records`` est réellement ouvert sur l'avis (et il n'existe
     AUCUNE classe ``*Activity`` maison dans ce module) ;
  2. la recherche globale trouve réellement un avis — la clé déclarée n'est
     pas une surface vide ;
  3. une déclaration NON câblée fait rougir : la matrice de dérive est verte
     aujourd'hui, et le devient rouge dès qu'on déclare une surface seule.
"""
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import RESPONSABLE_PERMISSIONS, Role
from apps.veille_ao.models import AvisMarche, SourceVeille, TypeSource
from apps.veille_ao.platform import PLATFORM
from authentication.models import Company, CustomUser
from core import platform, platform_coverage

CLE_AVIS = 'veille_ao.avismarche'


class ManifesteDeclareTests(SimpleTestCase):
    def test_module_aligne_sur_la_cle_de_manifeste(self):
        self.assertEqual(PLATFORM['module'], 'veille_ao')

    def test_les_deux_surfaces_couplees_sont_declarees(self):
        self.assertEqual(PLATFORM['record_targets'], [CLE_AVIS])
        self.assertEqual(PLATFORM['searchable_models'], [CLE_AVIS])

    def test_les_surfaces_non_cablees_restent_vides(self):
        """Une surface déclarée sans câblage est un mensonge (ARC41)."""
        self.assertEqual(PLATFORM['import_specs'], [])
        self.assertEqual(PLATFORM['customfield_models'], [])
        self.assertEqual(PLATFORM['agent_actions_module'], '')
        self.assertEqual(PLATFORM['automation_state_fields'], [])
        self.assertEqual(PLATFORM['kpi_providers'], [])

    def test_manifeste_collecte_par_le_registre(self):
        manifestes = platform.collect_platform_manifests()
        self.assertIn('veille_ao', manifestes)


class ChatterRecordsTests(TestCase):
    """Le chatter passe par ``records.Activity`` — jamais une classe maison."""

    def test_avis_est_une_cible_records(self):
        """``ALLOWED_TARGETS`` est l'union PARESSEUSE des ``record_targets``
        de tous les manifestes : déclarer la clé SUFFIT, il n'y a rien à
        modifier dans ``apps/records``. Le registre indexe des couples
        ``(app_label, model)``."""
        from apps.records.models import ALLOWED_TARGETS
        self.assertIn(('veille_ao', 'avismarche'), ALLOWED_TARGETS)

    def test_aucune_classe_activity_maison_dans_le_module(self):
        """ARC8 : les 13 chatters hand-rollés sont le premier poste de dette
        mesuré du dépôt — ce module ne l'aggrave pas."""
        from apps.veille_ao import models as modeles_veille
        fautifs = [
            nom for nom in dir(modeles_veille)
            if nom.endswith('Activity') or nom.endswith('Activite')
        ]
        self.assertEqual(fautifs, [], fautifs)

    def test_une_activite_peut_etre_ecrite_sur_un_avis(self):
        from apps.records.models import Activity
        from apps.records.services import log_note

        company = Company.objects.create(nom='ACME Chatter')
        user = CustomUser.objects.create_user(
            username='vao_chatter', password='x', company=company)
        source = SourceVeille.objects.create(
            company=company, code='src', libelle='Source',
            type_source=TypeSource.SAISIE_MANUELLE, actif=True)
        avis = AvisMarche.objects.create(
            company=company, source=source, objet='Centrale solaire',
            acheteur='Commune de Test')

        log_note(avis, user, 'Vu avec le partenaire.', company=company)

        self.assertEqual(Activity.objects.filter(company=company).count(), 1)


class RechercheGlobaleTests(TestCase):
    """La clé déclarée cherchable trouve réellement quelque chose."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Recherche')
        role = Role.objects.create(
            company=cls.company, nom='Responsable veille',
            permissions=list(RESPONSABLE_PERMISSIONS))
        cls.user = CustomUser.objects.create_user(
            username='vao_recherche', password='x', company=cls.company,
            role=role)
        source = SourceVeille.objects.create(
            company=cls.company, code='src', libelle='Source',
            type_source=TypeSource.SAISIE_MANUELLE, actif=True)
        cls.avis = AvisMarche.objects.create(
            company=cls.company, source=source,
            reference_avis='AO 12/2026',
            objet='Pompage solaire pour abreuvement du cheptel',
            acheteur='Commune de Figuig')

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def test_la_cle_est_dans_le_registre_local_de_recherche(self):
        from apps.reporting.search import _SEARCH_SPECS
        self.assertIn(CLE_AVIS, {cle for cle, _ in _SEARCH_SPECS})

    def test_la_cle_est_cherchable_pour_la_societe(self):
        self.assertIn(CLE_AVIS, platform.searchable_models(self.company))

    def test_un_avis_remonte_dans_la_recherche_globale(self):
        reponse = self._api().get(
            '/api/django/reporting/search/', {'q': 'pompage'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        groupes = {g['type'] for g in reponse.data['groups']}
        self.assertIn('avis_marche', groupes)

    def test_la_recherche_ne_traverse_pas_les_societes(self):
        autre = Company.objects.create(nom='Autre Recherche')
        autre_user = CustomUser.objects.create_user(
            username='vao_recherche_autre', password='x', company=autre,
            role=Role.objects.create(
                company=autre, nom='Responsable',
                permissions=list(RESPONSABLE_PERMISSIONS)))
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(autre_user)}')
        reponse = api.get('/api/django/reporting/search/',
                          {'q': 'pompage'})
        self.assertEqual(reponse.status_code, 200)
        groupes = {g['type'] for g in reponse.data['groups']}
        self.assertNotIn('avis_marche', groupes)


class MatriceDeDeriveTests(SimpleTestCase):
    """« Une déclaration non câblée fait rougir le test. »"""

    @staticmethod
    def _manifestes(record_targets, searchable_models):
        return {'veille_ao': {
            'module': 'veille_ao',
            'record_targets': record_targets,
            'searchable_models': searchable_models,
        }}

    def test_aucune_derive_nouvelle_aujourd_hui(self):
        self.assertEqual(platform_coverage.new_drift(), set())

    def test_declarer_le_chatter_seul_ferait_rougir(self):
        """Preuve que la garde MORD : un chatter sans recherche est une
        dérive NOUVELLE, hors baseline."""
        faux = self._manifestes([CLE_AVIS], [])
        self.assertIn((CLE_AVIS, 'chatter_sans_recherche'),
                      platform_coverage.all_drift(faux))
        self.assertIn((CLE_AVIS, 'chatter_sans_recherche'),
                      platform_coverage.new_drift(faux))

    def test_declarer_la_recherche_seule_ferait_rougir(self):
        faux = self._manifestes([], [CLE_AVIS])
        self.assertIn((CLE_AVIS, 'recherche_sans_chatter'),
                      platform_coverage.all_drift(faux))
        self.assertIn((CLE_AVIS, 'recherche_sans_chatter'),
                      platform_coverage.new_drift(faux))

    def test_les_deux_ensemble_ne_derivent_pas(self):
        faux = self._manifestes([CLE_AVIS], [CLE_AVIS])
        derives = platform_coverage.all_drift(faux)
        self.assertEqual([d for d in derives if d[0] == CLE_AVIS], [])
