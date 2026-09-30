"""ERR124 — le `produit` d'une ligne de retour de livraison / d'ordre de
démontage ne peut pas pointer vers un produit d'une AUTRE société (POST comme
PATCH → 400 nommant `produit`) ; sinon la validation du retour créditerait le
stock de cette autre société.

Run :
    python manage.py test \
        apps.installations.tests_autopilot_ligne_produit_cross_tenant -v2
"""
from django.test import TestCase

from apps.installations.models import (
    OrdreDemontageLigne, RetourLivraisonLigne,
)
from apps.installations.tests_autopilot_lignes_cross_tenant import (
    BASE, auth, make_company, make_ordre, make_produit, make_retour,
    make_user,
)


class TestRetourLigneProduitCrossTenant(TestCase):
    def setUp(self):
        self.co_a = make_company()
        self.co_b = make_company()
        self.api_a = auth(make_user(self.co_a))
        self.retour_a = make_retour(self.co_a)
        self.produit_a = make_produit(self.co_a, nom='Produit A')
        self.produit_b = make_produit(self.co_b, nom='Produit société B')
        self.ligne = RetourLivraisonLigne.objects.create(
            retour=self.retour_a, produit=self.produit_a,
            designation='Ligne A', quantite_livree=5)

    def test_post_produit_autre_societe_refuse(self):
        resp = self.api_a.post(f'{BASE}/retour-livraison-lignes/', {
            'retour': self.retour_a.id, 'produit': self.produit_b.id,
            'designation': 'Intrus', 'quantite_retournee': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('produit', resp.data)
        self.assertFalse(RetourLivraisonLigne.objects.filter(
            produit=self.produit_b).exists())

    def test_patch_produit_autre_societe_refuse(self):
        resp = self.api_a.patch(
            f'{BASE}/retour-livraison-lignes/{self.ligne.id}/',
            {'produit': self.produit_b.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('produit', resp.data)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.produit_id, self.produit_a.id)

    def test_patch_produit_meme_societe_ok(self):
        autre_a = make_produit(self.co_a, nom='Autre A')
        resp = self.api_a.patch(
            f'{BASE}/retour-livraison-lignes/{self.ligne.id}/',
            {'produit': autre_a.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.produit_id, autre_a.id)


class TestOrdreDemontageLigneProduitCrossTenant(TestCase):
    def setUp(self):
        self.co_a = make_company()
        self.co_b = make_company()
        self.api_a = auth(make_user(self.co_a))
        self.ordre_a = make_ordre(self.co_a)
        self.produit_a = make_produit(self.co_a, nom='Composant A')
        self.produit_b = make_produit(self.co_b, nom='Produit société B')
        self.ligne = OrdreDemontageLigne.objects.create(
            ordre=self.ordre_a, produit=self.produit_a,
            designation='Ligne A', quantite_attendue=1,
            quantite_recuperee=1)

    def test_post_produit_autre_societe_refuse(self):
        resp = self.api_a.post(f'{BASE}/ordre-demontage-lignes/', {
            'ordre': self.ordre_a.id, 'produit': self.produit_b.id,
            'designation': 'Intrus', 'quantite_recuperee': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('produit', resp.data)
        self.assertFalse(OrdreDemontageLigne.objects.filter(
            produit=self.produit_b).exists())

    def test_patch_produit_autre_societe_refuse(self):
        resp = self.api_a.patch(
            f'{BASE}/ordre-demontage-lignes/{self.ligne.id}/',
            {'produit': self.produit_b.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('produit', resp.data)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.produit_id, self.produit_a.id)

    def test_patch_produit_meme_societe_ok(self):
        autre_a = make_produit(self.co_a, nom='Autre A')
        resp = self.api_a.patch(
            f'{BASE}/ordre-demontage-lignes/{self.ligne.id}/',
            {'produit': autre_a.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.produit_id, autre_a.id)
