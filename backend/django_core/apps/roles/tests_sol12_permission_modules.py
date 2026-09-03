"""SOL12 — correspondance code de permission → module propriétaire.

Le backend GARDE tous les codes : cette table ne sert qu'à l'AFFICHAGE (le
frontend cache les cases d'une app que la société n'a pas). Deux invariants
comptent, et ils sont testés ici parce qu'une erreur y est silencieuse :

  1. chaque module cité existe RÉELLEMENT comme clé de manifeste — sinon la
     case ne serait jamais masquée (faute de frappe invisible) ;
  2. chaque code cité existe RÉELLEMENT dans `ALL_PERMISSIONS` — sinon
     l'entrée est morte.

Plus les correspondances PIÈGES, celles qu'un filtre par préfixe raterait.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.roles.models import ALL_PERMISSIONS, PERMISSION_MODULE
from apps.roles.views import RoleViewSet
from authentication.models import Company
from core import modules as modules_infra

User = get_user_model()


class TableCorrespondanceTests(TestCase):
    def test_chaque_module_cite_existe(self):
        manifests = modules_infra.collect_manifests()
        inconnus = sorted({
            module for module in PERMISSION_MODULE.values()
            if module not in manifests
        })
        self.assertEqual(
            inconnus, [],
            f'modules inconnus dans PERMISSION_MODULE : {inconnus}')

    def test_chaque_code_cite_existe(self):
        connus = set(ALL_PERMISSIONS)
        morts = sorted(c for c in PERMISSION_MODULE if c not in connus)
        self.assertEqual(
            morts, [], f'codes absents d\'ALL_PERMISSIONS : {morts}')

    def test_correspondances_pieges(self):
        """Celles qu'un filtre par préfixe se serait trompé à deviner."""
        self.assertEqual(PERMISSION_MODULE['installation_voir'], 'installations')
        self.assertEqual(PERMISSION_MODULE['intervention_gerer'], 'installations')
        self.assertEqual(PERMISSION_MODULE['technicien_assign'], 'installations')
        self.assertEqual(PERMISSION_MODULE['equipement_voir'], 'sav')
        self.assertEqual(PERMISSION_MODULE['projet_voir'], 'gestion_projet')
        self.assertEqual(PERMISSION_MODULE['btp_gerer'], 'btp_chantier')
        self.assertEqual(PERMISSION_MODULE['contrat_voir'], 'contrats')
        self.assertEqual(PERMISSION_MODULE['litige_voir'], 'litiges')
        self.assertEqual(PERMISSION_MODULE['cout_non_qualite_voir'], 'qhse')
        self.assertEqual(PERMISSION_MODULE['douane_responsable'], 'douane')
        self.assertEqual(PERMISSION_MODULE['transport_responsable'], 'transport')

    def test_fondation_et_donnees_sensibles_sans_module(self):
        """Ces codes ne doivent JAMAIS pouvoir être masqués par un toggle."""
        for code in ('roles_gerer', 'users_voir', 'users_gerer',
                     'parametres_voir', 'parametres_modifier',
                     'prix_achat_voir', 'marge_voir', 'client_pii_voir',
                     'salaires_voir', 'journal_activite_voir',
                     'records_scope_equipe', 'records_scope_sous_arbre'):
            self.assertNotIn(code, PERMISSION_MODULE, code)

    def test_les_modules_optionnels_sont_couverts(self):
        """Les modules éteints à la création (SOL8) doivent être masquables.

        Restreint aux modules qui POSSÈDENT des codes de permission propres :
        masquer un module n'a de sens que s'il a des cases à cacher (cf.
        ``test_pos_ne_porte_encore_aucun_code_a_masquer``)."""
        couverts = set(PERMISSION_MODULE.values())
        for module in ('paie', 'scm', 'douane', 'transport'):
            self.assertIn(module, couverts, module)

    def test_pos_ne_porte_encore_aucun_code_a_masquer(self):
        """`pos` est optionnel mais n'a AUCUN code de permission à lui.

        Ses vues sont gardées par le grossier ``IsResponsableOrAdmin`` (aucun
        ``pos_*`` dans ``ALL_PERMISSIONS``) : le picker n'affiche aucune case
        POS, il n'y a donc rien à masquer et rien à mapper — une entrée
        ``PERMISSION_MODULE`` pointant 'pos' devrait forcément citer le code
        d'un AUTRE module, ce qui masquerait ce module-là par erreur.

        Ce test TOMBE le jour où un code ``pos_*`` apparaît : il faudra alors
        l'ajouter à ``PERMISSION_MODULE``, sinon sa case resterait visible dans
        une société qui n'a pas le module."""
        codes_pos = sorted(c for c in ALL_PERMISSIONS if c.startswith('pos_'))
        self.assertEqual(
            codes_pos, [],
            'des codes POS existent désormais : mappez-les sur '
            f"PERMISSION_MODULE['<code>'] = 'pos' — {codes_pos}")
        self.assertNotIn('pos', set(PERMISSION_MODULE.values()))


class EndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='SOL12', slug='sol12')
        cls.admin = User.objects.create_user(
            username='sol12_admin', password='x',
            role_legacy=User.ROLE_ADMIN, company=cls.company)

    def _get(self):
        req = APIRequestFactory().get('/api/django/roles/permissions-disponibles/')
        force_authenticate(req, user=self.admin)
        vue = RoleViewSet.as_view({'get': 'permissions_disponibles'})
        return vue(req)

    def test_endpoint_sert_tous_les_codes_et_la_carte_des_modules(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200, resp.data)
        # Non-régression : la liste des codes est INCHANGÉE (le backend ne
        # filtre rien — SOL12 est un choix d'affichage).
        self.assertEqual(resp.data['permissions'], ALL_PERMISSIONS)
        self.assertEqual(resp.data['modules'], PERMISSION_MODULE)

    def test_carte_coherente_avec_les_codes_servis(self):
        resp = self._get()
        codes = set(resp.data['permissions'])
        for code in resp.data['modules']:
            self.assertIn(code, codes, code)
