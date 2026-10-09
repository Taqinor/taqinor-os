"""ACHT17 (C-ACHT-016) — en-tête d'un ordre d'assemblage / démontage figé
hors « planifié » ; tant qu'il est planifié, un changement de `quantite` ou
de `kit` recrée lignes et réservations, et la clôture consomme la
nomenclature du kit produit × la quantité produite.

Rejoue CKIT-1 : ordre de 1 passé à 10 → clôture : disjoncteurs 98 au lieu
de 80 ; 999/50 acceptés sur un ordre terminé ; kit A → B : composants A
consommés.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_ordre_entete"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, OrdreDemontage, ReservationAssemblage,
)
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/installations'
FIGE = 'Ordre figé : annulez-le et recréez-le'


class OrdreEnteteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht17', defaults={'nom': 'Co ACHT17'})
        self.user = User.objects.create_user(
            username='resp-acht17', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.coffret_a = self._produit('Coffret A', 0)
        self.coffret_b = self._produit('Coffret B', 0)
        self.disj = self._produit('Disjoncteur', 100)
        self.cable = self._produit('Câble', 100)
        self.kit_a = Kit.objects.create(
            company=self.company, nom='KA', produit_compose=self.coffret_a)
        KitComposant.objects.create(kit=self.kit_a, produit=self.disj,
                                    quantite=2)
        self.kit_b = Kit.objects.create(
            company=self.company, nom='KB', produit_compose=self.coffret_b)
        KitComposant.objects.create(kit=self.kit_b, produit=self.cable,
                                    quantite=3)

    def _produit(self, nom, stock):
        return Produit.objects.create(
            company=self.company, nom=nom, prix_vente=200, prix_achat=0,
            quantite_stock=stock)

    def _ordre(self, kit, quantite):
        r = self.api.post(f'{BASE}/ordres-assemblage/',
                          {'kit': kit.id, 'quantite': quantite},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return OrdreAssemblage.objects.get(pk=r.data['id'])

    def _terminer(self, ordre):
        r = self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
                          {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def _stock(self, produit):
        produit.refresh_from_db()
        return produit.quantite_stock

    def test_patch_quantite_planifie_reseed(self):
        ordre = self._ordre(self.kit_a, 1)
        r = self.api.patch(f'{BASE}/ordres-assemblage/{ordre.id}/',
                           {'quantite': 10}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lignes = list(ordre.lignes.values_list('produit_id', 'quantite'))
        self.assertEqual(len(lignes), 1)
        self.assertEqual((lignes[0][0], float(lignes[0][1])),
                         (self.disj.id, 20.0))
        resa = ReservationAssemblage.objects.get(
            ordre=ordre, produit=self.disj, active=True)
        self.assertEqual(float(resa.quantite), 20.0)
        self._terminer(ordre)
        self.assertEqual(self._stock(self.disj), 80)
        self.assertEqual(self._stock(self.coffret_a), 10)

    def test_patch_kit_planifie_reseed(self):
        ordre = self._ordre(self.kit_a, 2)
        r = self.api.patch(f'{BASE}/ordres-assemblage/{ordre.id}/',
                           {'kit': self.kit_b.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            set(ordre.lignes.values_list('produit_id', flat=True)),
            {self.cable.id})
        self.assertFalse(ReservationAssemblage.objects.filter(
            ordre=ordre, produit=self.disj, active=True,
            consomme=False).exists())
        self._terminer(ordre)
        self.assertEqual(self._stock(self.disj), 100)
        self.assertEqual(self._stock(self.cable), 94)
        self.assertEqual(self._stock(self.coffret_b), 2)
        self.assertEqual(self._stock(self.coffret_a), 0)

    def test_patch_termine_refuse(self):
        ordre = self._ordre(self.kit_a, 1)
        self._terminer(ordre)
        r = self.api.patch(f'{BASE}/ordres-assemblage/{ordre.id}/',
                           {'quantite_produite': 999, 'quantite': 50},
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(FIGE, str(r.data))
        ordre.refresh_from_db()
        self.assertEqual(ordre.quantite, 1)
        self.assertNotEqual(ordre.quantite_produite, 999)
        # Un champ non figé (note) reste modifiable.
        r = self.api.patch(f'{BASE}/ordres-assemblage/{ordre.id}/',
                           {'note': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_demontage_en_cours_refuse(self):
        self.coffret_a.quantite_stock = 5
        self.coffret_a.save(update_fields=['quantite_stock'])
        r = self.api.post(f'{BASE}/ordres-demontage/',
                          {'kit': self.kit_a.id, 'quantite': 1},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        ordre = OrdreDemontage.objects.get(pk=r.data['id'])
        # Planifié : la quantité se corrige et les lignes suivent.
        r = self.api.patch(f'{BASE}/ordres-demontage/{ordre.id}/',
                           {'quantite': 3}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ligne = ordre.lignes.get()
        self.assertEqual(float(ligne.quantite_attendue), 6.0)
        OrdreDemontage.objects.filter(pk=ordre.pk).update(
            statut=OrdreDemontage.Statut.TERMINE)
        r = self.api.patch(f'{BASE}/ordres-demontage/{ordre.id}/',
                           {'quantite': 4}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(FIGE, str(r.data))
        ordre.refresh_from_db()
        self.assertEqual(ordre.quantite, 3)
