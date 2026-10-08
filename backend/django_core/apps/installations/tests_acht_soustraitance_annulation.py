"""ACHT24 (C-ACHT-022) — composants confiés à un sous-traitant : rapatriés au
dépôt quand on annule un ordre démarré, `demarrer` refusé si un composant ne
peut pas être confié, rapport des sous-traitants calculé sur le solde réel
de leurs emplacements.

Rejoue CKIT-9 : 12 disjoncteurs restés « Chez Atelier… » après annulation,
rapport vide.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_soustraitance_annulation"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Kit, KitComposant, OrdreAssemblage
from apps.stock.models import Fournisseur, Produit
from apps.stock.services import stock_breakdown

User = get_user_model()
BASE = '/api/django/installations/ordres-assemblage'


class SousTraitanceAnnulationTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht24', defaults={'nom': 'Co ACHT24'})
        self.user = User.objects.create_user(
            username='resp-acht24', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.coffret = self._produit('Coffret', 0)
        self.disj = self._produit('Disjoncteur', 100)
        self.kit = Kit.objects.create(
            company=self.company, nom='KA', produit_compose=self.coffret)
        KitComposant.objects.create(kit=self.kit, produit=self.disj,
                                    quantite=3)
        self.atelier = Fournisseur.objects.create(
            company=self.company, nom='Atelier ACHT24',
            type=Fournisseur.Type.SERVICE)
        self._n = 0

    def _produit(self, nom, stock):
        return Produit.objects.create(
            company=self.company, nom=nom, prix_vente=200, prix_achat=0,
            quantite_stock=stock)

    def _ordre(self, kit=None, quantite=4):
        self._n += 1
        return OrdreAssemblage.objects.create(
            company=self.company, reference=f'ASM-ACHT24-{self._n}',
            kit=kit or self.kit, quantite=quantite,
            sous_traitant=self.atelier, created_by=self.user)

    def _par_emplacement(self, produit):
        produit.refresh_from_db()
        return {(ligne['is_principal'], ligne['emplacement_nom']):
                ligne['quantite'] for ligne in stock_breakdown(produit)}

    def _chez_atelier(self, produit):
        return self._par_emplacement(produit).get(
            (False, f'Chez {self.atelier.nom}'), 0)

    def _principal(self, produit):
        return sum(q for (principal, _nom), q
                   in self._par_emplacement(produit).items() if principal)

    def test_annulation_rapatrie(self):
        ordre = self._ordre()
        r = self.api.post(f'{BASE}/{ordre.id}/demarrer/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._chez_atelier(self.disj), 12)
        self.assertEqual(self._principal(self.disj), 88)
        r = self.api.post(f'{BASE}/{ordre.id}/annuler/',
                          {'motif_annulation': 'Annulé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._chez_atelier(self.disj), 0)
        self.assertEqual(self._principal(self.disj), 100)
        r = self.api.get(f'{BASE}/rapport-soustraitants/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data, [])

    def test_rapport_par_solde(self):
        ordre = self._ordre()
        self.api.post(f'{BASE}/{ordre.id}/demarrer/')
        # L'ordre est annulé « en base » sans rapatriement (donnée
        # historique) : le solde réel reste chez l'atelier → listé.
        OrdreAssemblage.objects.filter(pk=ordre.pk).update(
            statut=OrdreAssemblage.Statut.ANNULE)
        r = self.api.get(f'{BASE}/rapport-soustraitants/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['lignes'][0]['quantite'], 12)

    def test_demarrer_composant_manquant_refuse(self):
        rare = self._produit('Bornier rare', 0)
        kit2 = Kit.objects.create(
            company=self.company, nom='KB', produit_compose=self.coffret)
        KitComposant.objects.create(kit=kit2, produit=self.disj, quantite=1)
        KitComposant.objects.create(kit=kit2, produit=rare, quantite=1)
        ordre = self._ordre(kit=kit2, quantite=2)
        r = self.api.post(f'{BASE}/{ordre.id}/demarrer/')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Bornier rare', str(r.data))
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.PLANIFIE)
        self.assertEqual(self._chez_atelier(self.disj), 0)
