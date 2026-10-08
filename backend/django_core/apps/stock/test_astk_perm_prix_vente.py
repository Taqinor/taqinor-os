"""ASTK20 (D-ASTK-3) — écrire un prix de VENTE catalogue exige
``catalogue_prix_modifier``.

Rejoue PRIX-8 (audit stock 06/10/2026) : un Technicien responsable
(stock_modifier, sans le code) PATCH prix_vente → 200, prix=1100.00. Les
autres champs (seuil_alerte) restent sous stock_modifier.

Source réelle : rôles canoniques ``CANONICAL_SYSTEM_ROLES`` (ASTK16), bus
``core.events.produit_modifie`` observé (aucun mock).

Run :
    python manage.py test apps.stock.test_astk_perm_prix_vente -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import Produit
from authentication.models import Company
from core.events import produit_modifie

User = get_user_model()

URL = '/api/django/stock/produits/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PermPrixVenteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK20', slug='astk20-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)
        self.users = {}
        for nom in ('Technicien responsable', 'Administrateur'):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms[nom]),
                est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'astk20-{nom.lower().replace(" ", "-")}',
                password='x', company=self.company, role=role)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK20', sku='ASTK20-1',
            prix_vente=Decimal('1000'), seuil_alerte=2)
        self.evenements = []
        produit_modifie.connect(self._capter, dispatch_uid='astk20-capte')

    def tearDown(self):
        produit_modifie.disconnect(dispatch_uid='astk20-capte')

    def _capter(self, sender=None, **kwargs):
        self.evenements.append(kwargs)

    def _patch(self, user, data):
        return _api(user).patch(f'{URL}{self.produit.pk}/', data,
                                format='json')

    def _prix(self):
        self.produit.refresh_from_db()
        return self.produit.prix_vente

    def test_tech_resp_403_prix_vente(self):
        rep = self._patch(self.users['Technicien responsable'],
                          {'prix_vente': '1100.00'})
        self.assertEqual(rep.status_code, 403, rep.data)
        self.assertIn('catalogue_prix_modifier', str(rep.data['detail']))
        self.assertEqual(self._prix(), Decimal('1000'))
        self.assertEqual(self.evenements, [])

    def test_tech_resp_403_autres_champs_prix(self):
        for champ, valeur in (('prix_fixe_ht', '50.00'),
                              ('prix_par_panneau_ht', '12.00')):
            with self.subTest(champ=champ):
                rep = self._patch(self.users['Technicien responsable'],
                                  {champ: valeur})
                self.assertEqual(rep.status_code, 403, rep.data)
                self.produit.refresh_from_db()
                self.assertIsNone(getattr(self.produit, champ))

    def test_tech_resp_200_seuil_et_prix_inchange(self):
        rep = self._patch(self.users['Technicien responsable'],
                          {'seuil_alerte': 5})
        self.assertEqual(rep.status_code, 200, rep.data)
        # Un formulaire complet qui renvoie le prix INCHANGÉ passe.
        rep = self._patch(self.users['Technicien responsable'],
                          {'seuil_alerte': 6, 'prix_vente': '1000.00'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.seuil_alerte, 6)
        self.assertEqual(self.produit.prix_vente, Decimal('1000'))

    def test_tech_resp_403_bulk_set_price(self):
        rep = _api(self.users['Technicien responsable']).post(
            f'{URL}bulk/', {'action': 'set_price', 'ids': [self.produit.pk],
                            'mode': 'fixed', 'valeur': '1100'},
            format='json')
        self.assertEqual(rep.status_code, 403, rep.data)
        self.assertEqual(self._prix(), Decimal('1000'))

    def test_admin_200_prix(self):
        rep = self._patch(self.users['Administrateur'],
                          {'prix_vente': '1100.00'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(self._prix(), Decimal('1100'))
