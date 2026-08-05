"""NTADM3 — périmètre de données par entité pour les rôles.

Critère d'acceptation : un utilisateur restreint à la filiale A ne VOIT ni ne
peut CRÉER un devis rattaché à la filiale B ; un rôle sans restriction voit
tout comme avant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from ..services import creer_entite

User = get_user_model()

PERMS_COMMERCIAL = [
    'ventes_voir', 'ventes_creer', 'ventes_modifier',
    'crm_voir', 'crm_creer', 'users_voir',
]


def _company(nom, slug):
    """Nom ET slug EXPLICITEMENT distincts : le slug est UNIQUE, deux sociétés
    au même slug effectif seraient la MÊME ligne."""
    return Company.objects.create(nom=nom, slug=slug)


class Ntadm3PerimetreTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.roles.models import Role
        from apps.ventes.models import Devis

        self.company = _company('NTADM3 Co', 'ntadm3-co')
        self.filiale_a = creer_entite(self.company, nom='Filiale A', code='FA')
        self.filiale_b = creer_entite(self.company, nom='Filiale B', code='FB')

        self.role_a = Role.objects.create(
            company=self.company, nom='Commercial Filiale A',
            permissions=list(PERMS_COMMERCIAL))
        self.role_a.entites_visibles.add(self.filiale_a)
        self.role_libre = Role.objects.create(
            company=self.company, nom='Commercial sans périmètre',
            permissions=list(PERMS_COMMERCIAL))

        self.user_a = User.objects.create_user(
            username='ntadm3_a', password='pw', company=self.company,
            role=self.role_a, role_legacy='responsable')
        self.user_libre = User.objects.create_user(
            username='ntadm3_libre', password='pw', company=self.company,
            role=self.role_libre, role_legacy='responsable')

        self.client_metier = Client.objects.create(
            company=self.company, nom='Client NTADM3')
        self.devis_a = Devis.objects.create(
            company=self.company, reference='NTADM3-A',
            client=self.client_metier, entite=self.filiale_a)
        self.devis_b = Devis.objects.create(
            company=self.company, reference='NTADM3-B',
            client=self.client_metier, entite=self.filiale_b)
        self.devis_libre = Devis.objects.create(
            company=self.company, reference='NTADM3-LIBRE',
            client=self.client_metier)

        self.api_a = APIClient()
        self.api_a.force_authenticate(self.user_a)
        self.api_libre = APIClient()
        self.api_libre.force_authenticate(self.user_libre)

    # ── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _refs(resp):
        return {d['reference'] for d in resp.data['results']}

    # ── Lecture ────────────────────────────────────────────────────────────
    def test_role_restreint_ne_voit_que_sa_filiale_et_les_non_affectes(self):
        resp = self.api_a.get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._refs(resp), {'NTADM3-A', 'NTADM3-LIBRE'})

    def test_role_sans_perimetre_voit_tout_comme_avant(self):
        resp = self.api_libre.get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._refs(resp), {'NTADM3-A', 'NTADM3-B', 'NTADM3-LIBRE'})

    def test_detail_hors_perimetre_repond_404_pas_403(self):
        """404 et jamais 403 : aucun oracle d'existence."""
        resp = self.api_a.get(
            f'/api/django/ventes/devis/{self.devis_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_detail_dans_le_perimetre_reste_accessible(self):
        resp = self.api_a.get(
            f'/api/django/ventes/devis/{self.devis_a.id}/')
        self.assertEqual(resp.status_code, 200)

    # ── Écriture ───────────────────────────────────────────────────────────
    def test_creation_vers_une_filiale_hors_perimetre_refusee(self):
        resp = self.api_a.post(
            '/api/django/ventes/devis/',
            {'client': self.client_metier.id, 'entite': self.filiale_b.id},
            format='json')
        self.assertEqual(resp.status_code, 403)

    def test_creation_dans_le_perimetre_autorisee(self):
        resp = self.api_a.post(
            '/api/django/ventes/devis/',
            {'client': self.client_metier.id, 'entite': self.filiale_a.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['entite'], self.filiale_a.id)

    def test_creation_sans_entite_toujours_autorisee(self):
        resp = self.api_a.post(
            '/api/django/ventes/devis/',
            {'client': self.client_metier.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['entite'])

    def test_role_sans_perimetre_peut_creer_partout(self):
        resp = self.api_libre.post(
            '/api/django/ventes/devis/',
            {'client': self.client_metier.id, 'entite': self.filiale_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    # ── Autres modèles NTADM2 ──────────────────────────────────────────────
    def test_leads_et_produits_suivent_le_meme_perimetre(self):
        from decimal import Decimal

        from apps.crm.models import Lead
        from apps.stock.models import Produit

        Lead.objects.create(
            company=self.company, nom='Lead A', entite=self.filiale_a)
        Lead.objects.create(
            company=self.company, nom='Lead B', entite=self.filiale_b)
        Produit.objects.create(
            company=self.company, nom='Produit A', sku='NTADM3-A',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            entite=self.filiale_a)
        Produit.objects.create(
            company=self.company, nom='Produit B', sku='NTADM3-B',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            entite=self.filiale_b)

        leads = self.api_a.get('/api/django/crm/leads/')
        self.assertEqual(
            {ligne['nom'] for ligne in leads.data['results']}, {'Lead A'})
        produits = self.api_a.get('/api/django/stock/produits/')
        self.assertEqual(
            {p['nom'] for p in produits.data['results']}, {'Produit A'})


class Ntadm3SerializerPerimetreTests(TestCase):
    """Le périmètre exposé par l'API des rôles reste borné à la société."""

    def setUp(self):
        from apps.roles.models import Role

        self.company = _company('NTADM3 Roles Co', 'ntadm3-roles-co')
        self.autre = _company('NTADM3 Autre Co', 'ntadm3-autre-co')
        self.entite_locale = creer_entite(
            self.company, nom='Locale', code='LOC')
        self.entite_etrangere = creer_entite(
            self.autre, nom='Étrangère', code='ETR')
        self.admin = User.objects.create_user(
            username='ntadm3_admin', password='pw', company=self.company,
            role_legacy='admin', is_staff=True)
        self.role = Role.objects.create(
            company=self.company, nom='Rôle testé', permissions=['crm_voir'])
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def test_perimetre_local_accepte(self):
        resp = self.api.patch(
            f'/api/django/roles/{self.role.id}/',
            {'entites_visibles': [self.entite_locale.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            list(self.role.entites_visibles.values_list('id', flat=True)),
            [self.entite_locale.id])

    def test_entite_d_une_autre_societe_refusee(self):
        resp = self.api.patch(
            f'/api/django/roles/{self.role.id}/',
            {'entites_visibles': [self.entite_etrangere.id]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.role.entites_visibles.count(), 0)
