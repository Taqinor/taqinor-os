"""ASTK88/ASTK89 — ``produit_modifie`` émis par la variation de prix EN MASSE
et par la correction du barème forfaitaire / de la TVA (C-ASTK-020).

Sonde CAT-5/PRIX-3 : bulk set_price → prix 1100.00 mais AUCUN événement
(le PATCH unitaire, lui, en émettait un) ; PATCH tva+prix_fixe_ht → aucun
événement non plus. Le bus ``core.events`` est réel : un récepteur de test s'y
abonne, rien n'est mocké.
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from authentication.models import Company, CustomUser as User
from core.events import produit_modifie

_seq = itertools.count(1)


class _BaseEvenements(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK88 {n}', slug=f'astk88-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk88_admin_{n}', password='x',
            email=f'astk88-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.evenements = []

        def recepteur(sender, **kwargs):
            self.evenements.append(kwargs)

        self._recepteur = recepteur
        produit_modifie.connect(recepteur, weak=False)
        self.addCleanup(produit_modifie.disconnect, recepteur)


class BulkPrixEvenementTests(_BaseEvenements):
    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550', sku='PAN-550',
            prix_achat=Decimal('600'), prix_vente=Decimal('1000'))

    def _bulk(self, **corps):
        return self.api.post(
            '/api/django/stock/produits/bulk/',
            {'ids': [self.produit.pk], 'action': 'set_price', **corps},
            format='json')

    def test_bulk_set_price_emet_produit_modifie(self):
        reponse = self._bulk(mode='percent', valeur=10)

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.prix_vente, Decimal('1100.00'))
        self.assertEqual(len(self.evenements), 1)
        evt = self.evenements[0]
        self.assertEqual(
            evt['champs'], {'prix_vente': ['1000.00', '1100.00']})
        self.assertEqual(evt['company'], self.company)
        self.assertEqual(evt['user'], self.user)
        self.assertEqual(evt['produit'].pk, self.produit.pk)

    def test_bulk_sans_changement_n_emet_rien(self):
        reponse = self._bulk(mode='percent', valeur=0)

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(self.evenements, [])


class ChampsSuivisTests(_BaseEvenements):
    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Forfait pose', sku='FORF-1',
            prix_achat=Decimal('1000'), prix_vente=Decimal('2500'),
            prix_fixe_ht=Decimal('2000'), prix_par_panneau_ht=Decimal('250'),
            tva=Decimal('20'))

    def _patch(self, **corps):
        return self.api.patch(
            f'/api/django/stock/produits/{self.produit.pk}/', corps,
            format='json')

    def test_patch_tva_et_forfait_emet(self):
        reponse = self._patch(tva='10', prix_fixe_ht='2200')

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.tva, Decimal('10'))
        self.assertEqual(self.produit.prix_fixe_ht, Decimal('2200'))
        self.assertEqual(len(self.evenements), 1)
        self.assertEqual(
            self.evenements[0]['champs'],
            {'tva': ['20.00', '10.00'],
             'prix_fixe_ht': ['2000.00', '2200.00']})

    def test_patch_sans_changement_de_ces_champs_n_emet_rien(self):
        reponse = self._patch(seuil_alerte=5)

        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(self.evenements, [])
