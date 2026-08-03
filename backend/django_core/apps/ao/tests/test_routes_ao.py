"""AOF31 — routage AO complet : routes, basenames, permissions, contrat.

Constat qui a motivé cette tâche : une quinzaine de ressources AO étaient
supposées « au passage » par les tâches SCHEMA, sans qu'aucune ne soit chargée
de les ENREGISTRER — et le routeur ``compta`` expose déjà des basenames AO qui
pourraient collisionner. Une collision de basename est silencieuse :
``reverse()`` renvoie la mauvaise URL, personne ne s'en aperçoit avant la prod.

Ce module vérifie donc, explicitement :
  1. chaque ressource AO répond sous ``/api/django/ao/…`` ;
  2. AUCUN basename n'entre en collision avec le routeur ``compta`` ;
  3. la matrice ``ao_voir`` / ``ao_gerer`` tient sur CHAQUE route ;
  4. la pagination transverse s'applique ;
  5. le contrat d'API publié est dérivé du routeur (donc jamais périmé).

Run :
    python manage.py test apps.ao.tests.test_routes_ao -v2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.permissions import AO_GERER, AO_RENTABILITE_VOIR, AO_VOIR
from apps.ao.urls import router as router_ao
from apps.roles.models import COMMERCIAL_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/ao/'

#: Ressources du DOMAINE AO : socle ``AoBaseViewSet``, gardées par
#: ``ao_voir``/``ao_gerer``.
PREFIXES_DOMAINE = {
    'appels-offres', 'pieces-consultation', 'exigences-cps', 'batiments',
    'toitures', 'plans-source', 'obstacles', 'chaines-cotes', 'releves',
    'series-questions', 'questions', 'kits-calepinage', 'presets-calepinage',
    'modeles-pack', 'sections-memoire',
    'variantes-calepinage', 'bordereaux-prix', 'sections-bordereau',
    'lignes-bordereau', 'cautions-soumission', 'dossiers-soumission',
    'pieces-soumission', 'echeances-ao', 'resultats-ao', 'dossiers-ao',
    'pieces-dossier-ao', 'checklist-partenaire', 'pieces-administratives',
}

#: AOF157 — ressources de l'ÉCONOMIE DIRECTEUR. Elles sont DÉLIBÉRÉMENT hors du
#: socle ``AoBaseViewSet`` : coût de revient, marge et bénéfice sont gardés par
#: ``ao_rentabilite_voir`` (permission ÉLEVÉE), pas par ``ao_voir``. Les lister
#: à part n'est pas une exemption de complaisance — ``TestGardeRentabilite``
#: ci-dessous vérifie POSITIVEMENT qu'un lecteur ``ao_voir`` y est refusé.
PREFIXES_DIRECTEUR = {
    'economie', 'lignes-cout-revient', 'cibles-financieres',
}

#: Toutes les ressources attendues sous ``/api/django/ao/``.
PREFIXES_ATTENDUS = PREFIXES_DOMAINE | PREFIXES_DIRECTEUR


class TestRegistreDuRouteur(SimpleTestCase):
    def test_toutes_les_ressources_sont_enregistrees(self):
        prefixes = {p for p, _, _ in router_ao.registry}
        self.assertEqual(prefixes, PREFIXES_ATTENDUS)

    def test_tous_les_basenames_sont_prefixes_ao(self):
        for prefixe, _, basename in router_ao.registry:
            self.assertTrue(
                basename.startswith('ao-'),
                f'{prefixe} : basename « {basename} » sans préfixe « ao- ».')

    def test_aucune_collision_de_basename_avec_compta(self):
        """Une collision est SILENCIEUSE : ``reverse()`` renvoie l'autre URL."""
        from apps.compta.urls import router as router_compta

        basenames_ao = {b for _, _, b in router_ao.registry}
        basenames_compta = {b for _, _, b in router_compta.registry}
        self.assertEqual(basenames_ao & basenames_compta, set())

    def test_aucun_basename_duplique_dans_ao(self):
        basenames = [b for _, _, b in router_ao.registry]
        self.assertEqual(len(basenames), len(set(basenames)))

    def test_chaque_viewset_est_au_socle_ao(self):
        from apps.ao.viewsets import AoBaseViewSet

        for prefixe, viewset, _ in router_ao.registry:
            if prefixe in PREFIXES_DIRECTEUR:
                continue  # garde PLUS haute — voir le test suivant
            self.assertTrue(issubclass(viewset, AoBaseViewSet), prefixe)
            self.assertEqual(viewset.read_permission, AO_VOIR, prefixe)
            self.assertEqual(viewset.write_permission, AO_GERER, prefixe)

    def test_les_vues_directeur_portent_la_garde_de_rentabilite(self):
        """AOF157 — l'économie n'est JAMAIS gardée par le simple ``ao_voir``."""
        from apps.ao.permissions import CanViewAoRentabilite

        vues = {p: v for p, v, _ in router_ao.registry
                if p in PREFIXES_DIRECTEUR}
        self.assertEqual(set(vues), PREFIXES_DIRECTEUR)
        for prefixe, viewset in vues.items():
            self.assertIn(CanViewAoRentabilite, viewset.permission_classes,
                          prefixe)
            self.assertNotEqual(getattr(viewset, 'read_permission', None),
                                AO_VOIR, prefixe)


class BaseRoutes(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF31 Co', slug='aof31-co')

    def _api(self, permissions):
        role = Role.objects.create(
            company=self.company, nom=f'R{len(permissions)}{id(permissions)}',
            permissions=list(permissions))
        user = User.objects.create_user(
            username=f'aof31_{id(permissions)}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api


class TestMatriceDePermissions(BaseRoutes):
    def test_lecteur_ao_voir_lit_toutes_les_routes(self):
        api = self._api([AO_VOIR])
        for prefixe in sorted(PREFIXES_DOMAINE):
            reponse = api.get(f'{BASE}{prefixe}/')
            self.assertEqual(reponse.status_code, 200, prefixe)

    def test_lecteur_ao_voir_ne_peut_pas_ecrire(self):
        api = self._api([AO_VOIR])
        for prefixe in sorted(PREFIXES_ATTENDUS):
            reponse = api.post(f'{BASE}{prefixe}/', {}, format='json')
            self.assertEqual(reponse.status_code, 403, prefixe)

    def test_un_role_sans_permission_ao_est_refuse_partout(self):
        api = self._api(COMMERCIAL_PERMISSIONS)
        for prefixe in sorted(PREFIXES_ATTENDUS):
            self.assertEqual(
                api.get(f'{BASE}{prefixe}/').status_code, 403, prefixe)

    def test_anonyme_refuse(self):
        anonyme = APIClient()
        for prefixe in sorted(PREFIXES_ATTENDUS):
            self.assertIn(
                anonyme.get(f'{BASE}{prefixe}/').status_code, (401, 403),
                prefixe)


class TestGardeRentabilite(BaseRoutes):
    """AOF157 — la marge ne suit PAS la surface de lecture générale."""

    def test_un_lecteur_ao_voir_est_refuse_sur_l_economie(self):
        api = self._api([AO_VOIR, AO_GERER])
        for prefixe in sorted(PREFIXES_DIRECTEUR):
            self.assertEqual(
                api.get(f'{BASE}{prefixe}/').status_code, 403, prefixe)

    def test_la_permission_de_rentabilite_ouvre_l_economie(self):
        api = self._api([AO_RENTABILITE_VOIR])
        for prefixe in sorted(PREFIXES_DIRECTEUR):
            self.assertEqual(
                api.get(f'{BASE}{prefixe}/').status_code, 200, prefixe)


class TestPaginationTransverse(BaseRoutes):
    def test_la_liste_est_paginee(self):
        from apps.ao.models import AppelOffre

        for i in range(3):
            AppelOffre.objects.create(
                company=self.company, reference=f'AO-31-{i}', objet='X')
        reponse = self._api([AO_VOIR]).get(f'{BASE}appels-offres/')
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('results', reponse.data)
        self.assertIn('count', reponse.data)
        self.assertEqual(reponse.data['count'], 3)

    def test_page_size_respecte(self):
        from apps.ao.models import AppelOffre

        for i in range(5):
            AppelOffre.objects.create(
                company=self.company, reference=f'AO-31-P{i}', objet='X')
        reponse = self._api([AO_VOIR]).get(
            f'{BASE}appels-offres/', {'page_size': 2})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data['results']), 2)


class TestContratPublie(BaseRoutes):
    def test_le_contrat_liste_toutes_les_ressources(self):
        reponse = self._api([AO_VOIR]).get(f'{BASE}contrat/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        prefixes = {r['prefixe'] for r in reponse.data['ressources']}
        self.assertEqual(prefixes, PREFIXES_ATTENDUS)

    def test_le_contrat_declare_les_permissions_et_la_pagination(self):
        reponse = self._api([AO_VOIR]).get(f'{BASE}contrat/')
        self.assertEqual(reponse.data['permissions'],
                         {'lecture': AO_VOIR, 'ecriture': AO_GERER})
        self.assertEqual(reponse.data['pagination']['parametres'],
                         ['page', 'page_size'])

    def test_le_contrat_expose_filtres_et_actions(self):
        reponse = self._api([AO_VOIR]).get(f'{BASE}contrat/')
        par_prefixe = {r['prefixe']: r for r in reponse.data['ressources']}
        appels = par_prefixe['appels-offres']
        self.assertIn('reference_acheteur', appels['recherche'])
        self.assertIn('changer_statut', appels['actions'])
        self.assertEqual(appels['modele'], 'ao.appeloffre')

    def test_le_contrat_est_garde_comme_le_domaine(self):
        api = self._api(COMMERCIAL_PERMISSIONS)
        self.assertEqual(api.get(f'{BASE}contrat/').status_code, 403)
