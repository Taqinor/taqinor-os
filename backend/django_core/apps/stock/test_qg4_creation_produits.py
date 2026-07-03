"""QG4 — la CRÉATION de produits est réservée aux rôles Directeur +
Commercial responsable (décision Reda), sur TOUTES les portes d'entrée :

* le create REST (``ProduitViewSet.create`` — l'import OCR réutilise ce
  chemin) ;
* le commit d'import de données (``dataimport`` cible ``products``).

Seule la CRÉATION est durcie : lecture, modification et suppression gardent
leurs règles historiques. Le superuser passe toujours ; les comptes hérités
sans rôle fin sont refusés (garde de restriction, pas de compatibilité). Le
seeding ``init_roles`` porte la politique : « Commercial responsable » gagne
``stock_creer``, les autres rôles (hors Directeur) le perdent.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

URL_PRODUITS = '/api/django/stock/produits/'
URL_IMPORT_COMMIT = '/api/django/imports/commit/'

ROLES_AUTORISES = ('Directeur', 'Commercial responsable')
ROLES_REFUSES = (
    'Administrateur', 'Commercial', 'Technicien responsable', 'Technicien',
    'Viewer', 'Responsable', 'Utilisateur',
)


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class QG4Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='qg4-co', defaults={'nom': 'QG4 Co'})[0]
        cls.roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            cls.roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)

    def user_for(self, nom_role, username):
        return User.objects.create_user(
            username=username, password='x', company=self.company,
            role=self.roles[nom_role])

    def _payload(self, sku):
        return {'nom': f'Produit {sku}', 'prix_vente': '100', 'sku': sku}


class TestCreationRest(QG4Base):
    """Porte d'entrée n°1 : le create REST (réutilisé par l'import OCR)."""

    def test_directeur_et_commercial_responsable_creent(self):
        for i, nom_role in enumerate(ROLES_AUTORISES):
            user = self.user_for(nom_role, f'qg4_ok_{i}')
            r = api_for(user).post(
                URL_PRODUITS, self._payload(f'QG4-OK-{i}'), format='json')
            self.assertEqual(r.status_code, 201, (nom_role, r.data))
            produit = Produit.objects.get(id=r.data['id'])
            # Multi-tenant : la société est posée côté serveur.
            self.assertEqual(produit.company_id, self.company.id)

    def test_superuser_cree_toujours(self):
        su = User.objects.create_superuser(
            username='qg4_su', password='x', email='qg4su@x.ma',
            company=self.company)
        r = api_for(su).post(
            URL_PRODUITS, self._payload('QG4-SU'), format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_tous_les_autres_roles_403(self):
        for i, nom_role in enumerate(ROLES_REFUSES):
            user = self.user_for(nom_role, f'qg4_ko_{i}')
            r = api_for(user).post(
                URL_PRODUITS, self._payload(f'QG4-KO-{i}'), format='json')
            self.assertEqual(r.status_code, 403, (nom_role, r.status_code))
        self.assertFalse(
            Produit.objects.filter(sku__startswith='QG4-KO-').exists())

    def test_legacy_sans_role_fin_403(self):
        # Garde de restriction : un compte hérité sans rôle fin (même
        # role_legacy='admin') ne crée plus de produit — seul le superuser
        # court-circuite.
        legacy = User.objects.create_user(
            username='qg4_legacy', password='x', role_legacy='admin',
            company=self.company)
        r = api_for(legacy).post(
            URL_PRODUITS, self._payload('QG4-LEG'), format='json')
        self.assertEqual(r.status_code, 403)

    def test_lecture_modification_suppression_inchangees(self):
        # IMPORTANT : seule la CRÉATION est restreinte — les autres actions
        # gardent leurs règles historiques.
        produit = Produit.objects.create(
            company=self.company, nom='Existant QG4', sku='QG4-EXIST',
            prix_vente=10)
        admin = self.user_for('Administrateur', 'qg4_admin_rw')
        api = api_for(admin)
        self.assertEqual(api.get(URL_PRODUITS).status_code, 200)
        r = api.patch(f'{URL_PRODUITS}{produit.id}/',
                      {'seuil_alerte': 3}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # Le Responsable (rôle système hérité) garde la modification.
        resp_user = self.user_for('Responsable', 'qg4_resp_rw')
        r = api_for(resp_user).patch(
            f'{URL_PRODUITS}{produit.id}/', {'seuil_alerte': 5},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # La suppression reste admin (IsAdminRole).
        r = api.delete(f'{URL_PRODUITS}{produit.id}/')
        self.assertIn(r.status_code, (200, 204), r.status_code)


class TestImportDonnees(QG4Base):
    """Porte d'entrée n°2 : le commit d'import de données (cible products)."""

    def _csv(self, content):
        return SimpleUploadedFile(
            'data.csv', content.encode('utf-8'), content_type='text/csv')

    def test_import_products_directeur_ok(self):
        user = self.user_for('Directeur', 'qg4_imp_dir')
        f = self._csv('Nom,SKU,Prix\nPanneau QG4,QG4-IMP-1,1200\n')
        r = api_for(user).post(
            URL_IMPORT_COMMIT, {'file': f, 'target': 'products'},
            format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['created'], 1)

    def test_import_products_commercial_responsable_ok(self):
        user = self.user_for('Commercial responsable', 'qg4_imp_cr')
        f = self._csv('Nom,SKU,Prix\nPanneau QG4,QG4-IMP-2,1200\n')
        r = api_for(user).post(
            URL_IMPORT_COMMIT, {'file': f, 'target': 'products'},
            format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['created'], 1)

    def test_import_products_responsable_403(self):
        user = self.user_for('Responsable', 'qg4_imp_resp')
        f = self._csv('Nom,SKU,Prix\nRefusé,QG4-IMP-KO,1\n')
        r = api_for(user).post(
            URL_IMPORT_COMMIT, {'file': f, 'target': 'products'},
            format='multipart')
        self.assertEqual(r.status_code, 403, getattr(r, 'data', None))
        self.assertFalse(Produit.objects.filter(sku='QG4-IMP-KO').exists())

    def test_import_products_administrateur_403(self):
        user = self.user_for('Administrateur', 'qg4_imp_adm')
        f = self._csv('Nom,SKU,Prix\nRefusé,QG4-IMP-KO2,1\n')
        r = api_for(user).post(
            URL_IMPORT_COMMIT, {'file': f, 'target': 'products'},
            format='multipart')
        self.assertEqual(r.status_code, 403)

    def test_import_clients_responsable_toujours_ok(self):
        # Non-régression : seuls les PRODUITS sont durcis — les autres cibles
        # gardent la règle historique (responsable/admin).
        user = self.user_for('Responsable', 'qg4_imp_resp2')
        f = self._csv('Nom,Email\nClient QG4,c-qg4@x.ma\n')
        r = api_for(user).post(
            URL_IMPORT_COMMIT, {'file': f, 'target': 'clients'},
            format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['created'], 1)


class TestSeedingRoles(TestCase):
    """QG4 — le seeding des rôles porte la politique : seuls Directeur et
    Commercial responsable portent ``stock_creer``."""

    def test_constantes_canoniques(self):
        porteurs = [nom for nom, perms in CANONICAL_SYSTEM_ROLES
                    if 'stock_creer' in perms]
        self.assertEqual(sorted(porteurs),
                         ['Commercial responsable', 'Directeur'])

    def test_init_roles_repare_les_roles_deployes(self):
        # Un rôle système « Commercial responsable » déployé AVANT QG4 (sans
        # stock_creer) et un « Responsable » d'avant (avec stock_creer)
        # convergent vers la nouvelle politique au passage d'init_roles.
        company = Company.objects.get_or_create(
            slug='qg4-seed-co', defaults={'nom': 'QG4 Seed Co'})[0]
        User.objects.create_user(
            username='qg4_seed_u', password='x', company=company,
            role_legacy='responsable')
        Role.objects.create(
            company=company, nom='Commercial responsable', est_systeme=True,
            permissions=['crm_voir', 'ventes_voir'])
        Role.objects.create(
            company=company, nom='Responsable', est_systeme=True,
            permissions=['stock_voir', 'stock_creer', 'stock_modifier'])
        call_command('init_roles')
        cr = Role.objects.get(company=company, nom='Commercial responsable')
        self.assertIn('stock_creer', cr.permissions)
        for nom in ('Administrateur', 'Technicien responsable',
                    'Responsable'):
            role = Role.objects.get(company=company, nom=nom)
            self.assertNotIn('stock_creer', role.permissions, nom)
        directeur = Role.objects.get(company=company, nom='Directeur')
        self.assertIn('stock_creer', directeur.permissions)
