"""ASTK46 — `kitting.terminer` (lignes d'ordre personnalisées) ne fait plus
d'arrondi muet `round(...)` : une quantité de composant remise à l'échelle
non entière est refusée en 400 lisible, rien n'est consommé.

Avant : ordre de 2, ligne de 3, clôture à 1 produit → 3 × 1/2 = 1,5 arrondi
en silence à 2 (round au pair) et consommé.

Run :
    python manage.py test apps.installations.test_astk46_kitting_decimal
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, OrdreAssemblageLigne,
)
from apps.stock.models import MouvementStock, Produit

User = get_user_model()
BASE = '/api/django/installations'


class KittingDecimalTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-astk46', defaults={'nom': 'Co ASTK46'})
        self.user = User.objects.create_user(
            username='resp-astk46', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.composite = Produit.objects.create(
            company=self.company, nom='Coffret ASTK46', prix_vente=200,
            prix_achat=0, quantite_stock=0)
        self.comp = Produit.objects.create(
            company=self.company, nom='Disjoncteur ASTK46', prix_vente=20,
            prix_achat=0, quantite_stock=100)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret',
            produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp,
                                    quantite=1)

    def _ordre(self, ref, quantite, qte_ligne):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference=ref, kit=self.kit,
            quantite=quantite)
        OrdreAssemblageLigne.objects.create(
            ordre=ordre, produit=self.comp, designation=self.comp.nom,
            quantite=qte_ligne)
        return ordre

    def _terminer(self, ordre, quantite_produite):
        return self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
            {'quantite_produite': quantite_produite}, format='json')

    def test_quantite_non_entiere_refusee_400(self):
        ordre = self._ordre('ASM-ASTK46-1', quantite=2, qte_ligne=3)
        resp = self._terminer(ordre, 1)
        self.assertEqual(resp.status_code, 400, resp.content)
        texte = json.dumps(json.loads(resp.content), ensure_ascii=False)
        self.assertIn('non entière', texte)
        self.assertIn('1,5', texte)
        self.assertIn('Disjoncteur ASTK46', texte)
        # Persistance : stock des composants et ordre inchangés.
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.quantite_stock, 100)
        self.composite.refresh_from_db()
        self.assertEqual(self.composite.quantite_stock, 0)
        ordre.refresh_from_db()
        self.assertNotEqual(ordre.statut, OrdreAssemblage.Statut.TERMINE)
        self.assertFalse(ordre.stock_mouvemente)
        self.assertFalse(MouvementStock.objects.filter(
            reference=ordre.reference).exists())

    def test_quantite_entiere_consommee(self):
        ordre = self._ordre('ASM-ASTK46-2', quantite=2, qte_ligne=4)
        resp = self._terminer(ordre, 1)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.comp.refresh_from_db()
        self.assertEqual(self.comp.quantite_stock, 98)
