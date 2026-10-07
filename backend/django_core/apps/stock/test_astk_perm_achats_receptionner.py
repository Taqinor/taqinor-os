"""ASTK18 (D-ASTK-3) — les gestes « réceptionner » exigent ``achats_receptionner``.

Rejoue TEN-9b (audit stock 06/10/2026) : un Commercial « envoyer + recevoir
BCF → 200, stock pA 10 → 13 ». Désormais seuls Administrateur et Technicien
responsable (porteurs du code depuis ASTK16) réceptionnent ; légacy inchangé.

Source réelle : rôles canoniques ``CANONICAL_SYSTEM_ROLES``,
``HasPermissionOrLegacy`` ; aucun mock.

Run :
    python manage.py test apps.stock.test_astk_perm_achats_receptionner -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
    ReceptionFournisseur,
)
from authentication.models import Company

User = get_user_model()

BCF = '/api/django/stock/bons-commande-fournisseur/'
REC = '/api/django/stock/receptions-fournisseur/'
RET = '/api/django/stock/retours-fournisseur/'
REFUSES = ('Commercial', 'Technicien')
AUTORISES = ('Technicien responsable', 'Administrateur')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PermAchatsReceptionnerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK18', slug='astk18-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)
        self.users = {}
        for nom in REFUSES + AUTORISES:
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms[nom]),
                est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'astk18-{nom.lower().replace(" ", "-")}',
                password='x', company=self.company, role=role)
        self.legacy = User.objects.create_user(
            username='astk18-legacy', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK18')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK18', sku='ASTK18-1',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1000'),
            quantite_stock=10)

    def _bcf_envoye(self, ref):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=ref,
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))
        return bc, ligne

    def _stock(self):
        self.produit.refresh_from_db()
        return self.produit.quantite_stock

    def _recevoir(self, user, bc, ligne):
        return _api(user).post(
            f'{BCF}{bc.pk}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 3}]},
            format='json')

    def test_commercial_403_confirmer(self):
        rep = _api(self.users['Commercial']).post(
            f'{REC}999999/confirmer/', {}, format='json')
        self.assertEqual(rep.status_code, 403)

    def test_roles_sans_code_403(self):
        bc, ligne = self._bcf_envoye('BCF-ASTK18-R')
        nb_rec = ReceptionFournisseur.objects.count()
        for nom in REFUSES:
            api = _api(self.users[nom])
            reps = {
                'recevoir': self._recevoir(self.users[nom], bc, ligne),
                'reception_create': api.post(REC, {
                    'bon_commande': bc.pk}, format='json'),
                'reception_confirmer': api.post(
                    f'{REC}999999/confirmer/', {}, format='json'),
                'reception_annuler': api.post(
                    f'{REC}999999/annuler/', {}, format='json'),
                'controle_qualite': api.post(
                    f'{REC}999999/controle-qualite/', {}, format='json'),
                'retour_create': api.post(RET, {
                    'fournisseur': self.fournisseur.pk}, format='json'),
                'retour_valider': api.post(
                    f'{RET}999999/valider/', {}, format='json'),
            }
            for geste, rep in reps.items():
                with self.subTest(role=nom, geste=geste):
                    self.assertEqual(rep.status_code, 403, rep.data)
        # CLAUSE PERSISTANCE : stock et quantité reçue inchangés.
        self.assertEqual(self._stock(), 10)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 0)
        self.assertEqual(ReceptionFournisseur.objects.count(), nb_rec)

    def test_technicien_responsable_et_admin_recoivent(self):
        attendu = 10
        for i, user in enumerate([self.users[n] for n in AUTORISES]
                                 + [self.legacy]):
            with self.subTest(user=user.username):
                bc, ligne = self._bcf_envoye(f'BCF-ASTK18-OK{i}')
                rep = self._recevoir(user, bc, ligne)
                self.assertEqual(rep.status_code, 200, rep.data)
                attendu += 3
                self.assertEqual(self._stock(), attendu)
