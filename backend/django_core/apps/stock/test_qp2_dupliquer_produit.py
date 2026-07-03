"""QP2 — clone serveur d'un produit (« créer un nouveau produit dans le
stock » depuis une ligne de devis renommée). Réservé aux mêmes rôles que la
création (QG4 : Directeur + Commercial responsable) ; le SKU n'est JAMAIS
dupliqué (évite un doublon (company, sku)) et prix_achat est copié
SERVEUR (jamais transmis par le client)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

ROLES_AUTORISES = ('Directeur', 'Commercial responsable')
ROLES_REFUSES = ('Administrateur', 'Commercial', 'Responsable', 'Technicien')


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class QP2Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='qp2-co', defaults={'nom': 'QP2 Co'})[0]
        cls.other_company = Company.objects.get_or_create(
            slug='qp2-co-other', defaults={'nom': 'QP2 Other Co'})[0]
        cls.roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            cls.roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.source = Produit.objects.create(
            company=cls.company, nom='Onduleur Huawei 10kW',
            sku='QP2-SRC-1', prix_vente=15000, prix_achat=11000,
            marque='Huawei', garantie_mois=60,
        )

    def user_for(self, nom_role, username):
        return User.objects.create_user(
            username=username, password='x', company=self.company,
            role=self.roles[nom_role])

    def url(self, produit_id=None):
        pid = produit_id or self.source.id
        return f'/api/django/stock/produits/{pid}/dupliquer/'


class TestDupliquerAutorise(QP2Base):
    def test_directeur_clone_avec_nom_frais_sku_et_prix_achat_copie(self):
        user = self.user_for('Directeur', 'qp2_dir')
        r = api_for(user).post(
            self.url(), {'nom': 'Onduleur Huawei 10kW (Client X)'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        clone = Produit.objects.get(id=r.data['id'])
        self.assertEqual(clone.company_id, self.company.id)
        self.assertEqual(clone.nom, 'Onduleur Huawei 10kW (Client X)')
        self.assertIsNone(clone.sku)  # jamais dupliqué
        self.assertEqual(clone.prix_vente, self.source.prix_vente)
        self.assertEqual(clone.prix_achat, self.source.prix_achat)  # copié serveur
        self.assertEqual(clone.marque, self.source.marque)
        self.assertNotEqual(clone.id, self.source.id)

    def test_commercial_responsable_clone(self):
        user = self.user_for('Commercial responsable', 'qp2_cr')
        r = api_for(user).post(
            self.url(), {'nom': 'Onduleur Huawei 10kW (Client Y)'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_prix_achat_transmis_par_le_client_est_ignore(self):
        # Le corps ne porte que `nom` (whitelist) : même si un client
        # malicieux ajoute prix_achat, il est ignoré (copié depuis la source).
        user = self.user_for('Directeur', 'qp2_dir_leak')
        r = api_for(user).post(
            self.url(), {'nom': 'Clone tentative', 'prix_achat': '1'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        clone = Produit.objects.get(id=r.data['id'])
        self.assertEqual(clone.prix_achat, self.source.prix_achat)

    def test_nom_manquant_400(self):
        user = self.user_for('Directeur', 'qp2_dir_noname')
        r = api_for(user).post(self.url(), {}, format='json')
        self.assertEqual(r.status_code, 400)


class TestDupliquerRefuse(QP2Base):
    def test_roles_non_autorises_403(self):
        for i, nom_role in enumerate(ROLES_REFUSES):
            user = self.user_for(nom_role, f'qp2_ko_{i}')
            r = api_for(user).post(
                self.url(), {'nom': f'Clone refusé {i}'}, format='json')
            self.assertEqual(r.status_code, 403, (nom_role, r.status_code))
        self.assertFalse(
            Produit.objects.filter(nom__startswith='Clone refusé').exists())

    def test_superuser_clone_toujours(self):
        su = User.objects.create_superuser(
            username='qp2_su', password='x', email='qp2su@x.ma',
            company=self.company)
        r = api_for(su).post(
            self.url(), {'nom': 'Clone superuser'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_scoping_societe_produit_hors_societe_404(self):
        autre_produit = Produit.objects.create(
            company=self.other_company, nom='Produit autre société',
            prix_vente=100)
        user = self.user_for('Directeur', 'qp2_scope')
        r = api_for(user).post(
            self.url(autre_produit.id), {'nom': 'Tentative cross-tenant'},
            format='json')
        self.assertEqual(r.status_code, 404)
