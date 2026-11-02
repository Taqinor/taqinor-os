"""QX23be — instantané de marge (interne, manager-only).

  * ``compute_marge_snapshot`` = Σ HT − Σ(qté × prix_achat) ; None sans coût ;
  * ``mark_devis_sent`` fige la marge ;
  * le serializer n'expose la marge QU'AU responsable (jamais au commercial),
    jamais dans un PDF/sortie client (prix_achat rule).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.roles import permissions_registre as R
from apps.roles.models import Role
from apps.stock.models import Produit
from apps.ventes.domain.etudes import refresh_marge_snapshot
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.serializers import DevisSerializer, DevisWriteSerializer
from apps.ventes.services import compute_marge_snapshot, mark_devis_sent

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class Qx23MargeSnapshotTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx23-co', defaults={'nom': 'QX23 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX23',
            telephone='+212600000045')

    def _devis(self, ref, *, prix_achat='600', prix_vente='1000', qty='10'):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku=f'{ref}-PV',
            prix_vente=Decimal(prix_vente), prix_achat=Decimal(prix_achat),
            quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal(qty), prix_unitaire=Decimal(prix_vente),
            remise=Decimal('0'))
        return devis

    def test_compute_marge(self):
        # 10×1000 = 10000 HT ; coût 10×600 = 6000 → marge 4000.
        devis = self._devis(f'DEV-{MONTH}-QX2301')
        self.assertEqual(compute_marge_snapshot(devis), Decimal('4000.00'))

    def test_none_when_no_prix_achat(self):
        devis = self._devis(f'DEV-{MONTH}-QX2302', prix_achat='0')
        self.assertIsNone(compute_marge_snapshot(devis))

    def test_mark_sent_freezes_marge(self):
        devis = self._devis(f'DEV-{MONTH}-QX2303')
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.marge_snapshot, Decimal('4000.00'))

    def test_serializer_hides_marge_from_non_manager(self):
        devis = self._devis(f'DEV-{MONTH}-QX2304')
        devis.marge_snapshot = Decimal('4000.00')
        devis.save(update_fields=['marge_snapshot'])
        commercial = User.objects.create_user(
            username='qx23_com', password='x', role_legacy='commercial',
            company=self.company)
        req = type('R', (), {'user': commercial})()
        data = DevisSerializer(devis, context={'request': req}).data
        self.assertIsNone(data['marge_snapshot'])

    def test_serializer_shows_marge_to_manager(self):
        devis = self._devis(f'DEV-{MONTH}-QX2305')
        devis.marge_snapshot = Decimal('4000.00')
        devis.save(update_fields=['marge_snapshot'])
        manager = User.objects.create_user(
            username='qx23_resp', password='x', role_legacy='responsable',
            company=self.company)
        req = type('R', (), {'user': manager})()
        data = DevisSerializer(devis, context={'request': req}).data
        self.assertEqual(data['marge_snapshot'], '4000.00')

    def test_api_list_hides_marge_from_commercial(self):
        devis = self._devis(f'DEV-{MONTH}-QX2306')
        devis.marge_snapshot = Decimal('4000.00')
        devis.save(update_fields=['marge_snapshot'])
        commercial = User.objects.create_user(
            username='qx23_com2', password='x', role_legacy='commercial',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(commercial)}')
        resp = api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data.get('marge_snapshot'))

    # ── ADVS9 (C-ADVS-002) : la garde est ``marge_voir``, pas ``is_responsable``
    def _user_role_fin(self, username, permissions):
        role = Role.objects.create(
            company=self.company, nom=f'{username} role',
            permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.company, role=role)

    @staticmethod
    def _api(user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    @staticmethod
    def _marges_de_la_liste(reponse, devis):
        lignes = reponse.data.get('results', reponse.data)
        return [ln['marge_snapshot'] for ln in lignes if ln['id'] == devis.id]

    @staticmethod
    def _marges_serialisees(devis, user):
        req = type('R', (), {'user': user})()
        ctx = {'request': req}
        return (DevisSerializer(devis, context=ctx).data['marge_snapshot'],
                DevisWriteSerializer(devis, context=ctx).data['marge_snapshot'])

    def _devis_marge_figee(self, ref):
        devis = self._devis(ref)
        Devis.objects.filter(pk=devis.pk).update(marge_snapshot=Decimal('4000.00'))
        devis.refresh_from_db()
        return devis

    def test_role_fin_sans_marge_voir_ne_lit_jamais_la_marge(self):
        devis = self._devis_marge_figee(f'DEV-{MONTH}-QX2307')
        roles = {'advs9_com': R.COMMERCIAL_PERMISSIONS,
                 'advs9_rh': R.ADMIN_RH_PERMISSIONS,
                 'advs9_tech': R.TECHNICIEN_PERMISSIONS,
                 'advs9_terrain': R.COMMERCIAL_TERRAIN_PERMISSIONS}
        for username, permissions in roles.items():
            with self.subTest(role=username):
                self.assertNotIn('marge_voir', permissions)
                user = self._user_role_fin(username, permissions)
                self.assertTrue(user.is_responsable)  # le trou : vrai pour eux
                self.assertEqual(self._marges_serialisees(devis, user),
                                 (None, None))
        for username, permissions in (('advs9_dir', R.DIRECTEUR_PERMISSIONS),
                                      ('advs9_adm', R.ADMIN_PERMISSIONS)):
            with self.subTest(role=username):
                user = self._user_role_fin(username, permissions)
                self.assertEqual(self._marges_serialisees(devis, user),
                                 ('4000.00', '4000.00'))

    def test_comptes_legacy_gardent_la_regle_is_responsable(self):
        devis = self._devis_marge_figee(f'DEV-{MONTH}-QX2308')
        responsable = User.objects.create_user(
            username='advs9_leg_resp', password='x',
            role_legacy='responsable', company=self.company)
        commercial = User.objects.create_user(
            username='advs9_leg_com', password='x',
            role_legacy='commercial', company=self.company)
        self.assertEqual(self._marges_serialisees(devis, responsable),
                         ('4000.00', '4000.00'))
        self.assertEqual(self._marges_serialisees(devis, commercial),
                         (None, None))

    def test_api_masque_la_marge_en_lecture_et_dans_la_reponse_d_ecriture(self):
        """GET détail, GET liste, POST atomic, PATCH — rejeu de la sonde."""
        commercial = self._user_role_fin('advs9_api_com', R.COMMERCIAL_PERMISSIONS)
        directeur = self._user_role_fin('advs9_api_dir', R.DIRECTEUR_PERMISSIONS)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='ADVS9-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=100)
        api_com, api_dir = self._api(commercial), self._api(directeur)
        cree = api_com.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'taux_tva': '20.00',
            'lignes': [{'produit': produit.id, 'designation': produit.nom,
                        'quantite': '10', 'prix_unitaire': '1000.00',
                        'taux_tva': '20'}]}, format='json')
        self.assertEqual(cree.status_code, 201, cree.content)
        self.assertIsNone(cree.data['marge_snapshot'])
        devis = Devis.objects.get(pk=cree.data['id'])
        refresh_marge_snapshot(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.marge_snapshot, Decimal('4000.00'))
        url = f'/api/django/ventes/devis/{devis.id}/'
        liste_url = '/api/django/ventes/devis/'

        for api, attendu in ((api_com, None), (api_dir, '4000.00')):
            lu = api.get(url)
            self.assertEqual(lu.status_code, 200, lu.content)
            self.assertEqual(lu.data['marge_snapshot'], attendu)
            liste = api.get(liste_url)
            self.assertEqual(liste.status_code, 200, liste.content)
            self.assertEqual(self._marges_de_la_liste(liste, devis), [attendu])
            patch = api.patch(url, {'note': 'advs9'}, format='json')
            self.assertEqual(patch.status_code, 200, patch.content)
            self.assertEqual(patch.data['marge_snapshot'], attendu)
