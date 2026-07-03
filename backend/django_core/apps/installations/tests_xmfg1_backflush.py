"""
XMFG1 — Backflush : consommation/production de stock à la clôture d'un ordre
d'assemblage.

Couvre :
  * `terminer` décrémente les composants et incrémente le composite
    exactement une fois (mouvements MouvementStock corrects) ;
  * `quantite_produite` ≠ `quantite` planifiée est prise en compte ;
  * une re-clôture (statut déjà terminé, `stock_mouvemente=True`) n'émet
    aucun second mouvement ;
  * un kit sans `produit_compose` est rejeté proprement (400).

Run :
    python manage.py test apps.installations.tests_xmfg1_backflush -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Kit, KitComposant, OrdreAssemblage

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg1-co-{n}', defaults={'nom': nom or f'XMFG1 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg1-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0,
        quantite_stock=stock)


class TestBackflush(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret AC/DC', stock=0)
        self.comp1 = make_produit(self.company, nom='Disjoncteur', stock=50)
        self.comp2 = make_produit(self.company, nom='Presse-étoupe', stock=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)
        KitComposant.objects.create(kit=self.kit, produit=self.comp2, quantite=4)
        self.ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-TEST-1', kit=self.kit,
            quantite=3)

    def test_terminer_consomme_et_produit_une_seule_fois(self):
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/terminer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.ordre.refresh_from_db()
        self.comp1.refresh_from_db()
        self.comp2.refresh_from_db()
        self.composite.refresh_from_db()
        # quantite_produite défaut = quantite (3)
        self.assertEqual(self.ordre.quantite_produite, 3)
        self.assertTrue(self.ordre.stock_mouvemente)
        self.assertEqual(self.comp1.quantite_stock, 50 - 2 * 3)
        self.assertEqual(self.comp2.quantite_stock, 50 - 4 * 3)
        self.assertEqual(self.composite.quantite_stock, 0 + 3)

        # Re-clôture : aucun second mouvement.
        resp2 = self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/terminer/', {},
            format='json')
        self.assertEqual(resp2.status_code, 200, resp2.content)
        self.comp1.refresh_from_db()
        self.comp2.refresh_from_db()
        self.composite.refresh_from_db()
        self.assertEqual(self.comp1.quantite_stock, 50 - 2 * 3)
        self.assertEqual(self.comp2.quantite_stock, 50 - 4 * 3)
        self.assertEqual(self.composite.quantite_stock, 3)

    def test_quantite_produite_differente_geree(self):
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/terminer/',
            {'quantite_produite': 2}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.ordre.refresh_from_db()
        self.comp1.refresh_from_db()
        self.composite.refresh_from_db()
        self.assertEqual(self.ordre.quantite_produite, 2)
        self.assertEqual(self.comp1.quantite_stock, 50 - 2 * 2)
        self.assertEqual(self.composite.quantite_stock, 2)

    def test_kit_sans_produit_compose_rejette(self):
        kit_incomplet = Kit.objects.create(company=self.company, nom='Sans article')
        KitComposant.objects.create(
            kit=kit_incomplet, produit=self.comp1, quantite=1)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-TEST-2', kit=kit_incomplet,
            quantite=1)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.PLANIFIE)
        self.assertFalse(ordre.stock_mouvemente)

    def test_mouvements_stock_references_ordre(self):
        from apps.stock.models import MouvementStock
        self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/terminer/', {},
            format='json')
        mouvements = MouvementStock.objects.filter(reference=self.ordre.reference)
        # 2 sorties (composants) + 1 entree (composite)
        self.assertEqual(mouvements.count(), 3)
        sorties = mouvements.filter(type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        entrees = mouvements.filter(type_mouvement=MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(sorties.count(), 2)
        self.assertEqual(entrees.count(), 1)
