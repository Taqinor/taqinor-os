"""ASTK10 (D-ASTK-2) — prix et montants d'achat des BCF servis UNIQUEMENT avec
`prix_achat_voir`.

Rejoue TEN-7 (audit stock 06/10/2026) : les rôles canoniques Commercial,
Technicien et Viewer (sans `prix_achat_voir`) recevaient 200 + prix sur la
liste, le détail, le PDF interne, l'historique des prix, le rapport hors
contrat et la route /api/django/achats/.

Source réelle : `CustomUser.can_view_buy_prices` + permissions canoniques du
registre des rôles (aucun mock).

Run :
    python manage.py test apps.stock.test_astk_prix_achat_bcf -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from authentication.models import Company

User = get_user_model()

BASES = ('/api/django/stock/bons-commande-fournisseur/',
         '/api/django/achats/bons-commande-fournisseur/')
CLES_PRIX = {'prix_achat_unitaire', 'prix_achat_unitaire_devise',
             'total_achat', 'frais_annexes'}


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _cles(obj):
    """Toutes les clés d'un JSON imbriqué (dict/list)."""
    trouvees = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            trouvees.add(k)
            trouvees |= _cles(v)
    elif isinstance(obj, list):
        for v in obj:
            trouvees |= _cles(v)
    return trouvees


def _rows(data):
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PrixAchatBcfTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK10', slug='astk10-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)
        self.sans_prix = {}
        for nom in ('Commercial', 'Technicien', 'Viewer'):
            self.assertNotIn('prix_achat_voir', perms[nom])
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=perms[nom])
            self.sans_prix[nom] = User.objects.create_user(
                username=f'astk10-{nom.lower()}', password='x',
                company=self.company, role=role)
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=perms['Administrateur'])
        self.admin = User.objects.create_user(
            username='astk10-admin', password='x', company=self.company,
            role=role_admin)
        self.assertTrue(self.admin.can_view_buy_prices)
        # Compte légacy « normal » sans rôle fin : repli historique.
        self.legacy = User.objects.create_user(
            username='astk10-legacy', password='x', company=self.company,
            role_legacy='normal')
        self.assertTrue(self.legacy.can_view_buy_prices)

        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK10')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK10', sku='ASTK10-1',
            prix_vente=Decimal('1500'), prix_achat=Decimal('900'))
        hier = datetime.date.today() - datetime.timedelta(days=5)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK10-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=hier)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('820'), frais_annexes=Decimal('15'))

    # ── lectures servies, sans aucune clé de prix ──────────────────────────
    def test_liste_sans_prix_pour_commercial(self):
        for base in BASES:
            for nom, user in self.sans_prix.items():
                rep = _api(user).get(base)
                self.assertEqual(rep.status_code, 200, (base, nom))
                rows = _rows(rep.data)
                self.assertEqual(len(rows), 1)
                self.assertFalse(CLES_PRIX & _cles(rows), (base, nom))
                self.assertIn('lignes', rows[0])
                self.assertEqual(rows[0]['lignes'][0]['quantite'], 1)

    def test_detail_et_en_retard_sans_prix(self):
        for base in BASES:
            for nom, user in self.sans_prix.items():
                api = _api(user)
                rep = api.get(f'{base}{self.bcf.pk}/')
                self.assertEqual(rep.status_code, 200, (base, nom))
                self.assertFalse(CLES_PRIX & _cles(rep.data), (base, nom))
                rep = api.get(f'{base}en-retard/')
                self.assertEqual(rep.status_code, 200, (base, nom))
                self.assertEqual(len(rep.data), 1)
                self.assertFalse(CLES_PRIX & _cles(rep.data), (base, nom))

    # ── lectures dont l'objet est un prix : 403 ─────────────────────────────
    def test_pdf_interne_403(self):
        for base in BASES:
            for nom, user in self.sans_prix.items():
                rep = _api(user).get(f'{base}{self.bcf.pk}/pdf/')
                self.assertEqual(rep.status_code, 403, (base, nom))

    def test_historique_prix_403(self):
        for base in BASES:
            for nom, user in self.sans_prix.items():
                rep = _api(user).get(
                    f'{base}historique-prix/', {'produit': self.produit.pk})
                self.assertEqual(rep.status_code, 403, (base, nom))

    def test_achats_hors_contrat_403(self):
        for base in BASES:
            for nom, user in self.sans_prix.items():
                rep = _api(user).get(f'{base}achats-hors-contrat/')
                self.assertEqual(rep.status_code, 403, (base, nom))

    # ── avec prix_achat_voir et en légacy : inchangé ────────────────────────
    def test_avec_prix_achat_voir_et_legacy_inchanges(self):
        for user in (self.admin, self.legacy):
            api = _api(user)
            for base in BASES:
                rep = api.get(f'{base}{self.bcf.pk}/')
                self.assertEqual(rep.status_code, 200)
                ligne = rep.data['lignes'][0]
                self.assertEqual(Decimal(str(ligne['prix_achat_unitaire'])),
                                 Decimal('820'))
                self.assertEqual(Decimal(str(ligne['frais_annexes'])),
                                 Decimal('15'))
                self.assertIn('total_achat', rep.data)
                self.assertIn('prix_achat_unitaire_devise', ligne)
                rows = _rows(api.get(base).data)
                self.assertIn('total_achat', rows[0])
                rep = api.get(f'{base}historique-prix/',
                              {'produit': self.produit.pk})
                self.assertEqual(rep.status_code, 200)
                rep = api.get(f'{base}achats-hors-contrat/')
                self.assertEqual(rep.status_code, 200)
            rep = api.get(f'{BASES[0]}{self.bcf.pk}/pdf/')
            self.assertEqual(rep.status_code, 200)
            self.assertEqual(rep['Content-Type'], 'application/pdf')
