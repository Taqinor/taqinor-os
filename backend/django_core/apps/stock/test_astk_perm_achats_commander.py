"""ASTK17 (D-ASTK-3) — les gestes « commander » exigent ``achats_commander``.

Rejoue TEN-9 (audit stock 06/10/2026) : Commercial / Technicien / Technicien
responsable créaient un BCF (201) faute de code fin — `IsResponsableOrAdmin`
laissait passer tout rôle portant une permission d'écriture.

Source réelle : rôles canoniques ``CANONICAL_SYSTEM_ROLES`` (Administrateur
porte ``achats_commander`` depuis ASTK16), ``HasPermissionOrLegacy`` ; aucun
mock.

Run :
    python manage.py test apps.stock.test_astk_perm_achats_commander -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    ModeleBonCommandeFournisseur, Produit,
)
from authentication.models import Company

User = get_user_model()

BCF = '/api/django/stock/bons-commande-fournisseur/'
BCF_ACHATS = '/api/django/achats/bons-commande-fournisseur/'
MODELES = '/api/django/stock/modeles-bcf/'
REFUSES = ('Commercial', 'Commercial terrain', 'Technicien',
           'Technicien responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PermAchatsCommanderTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK17', slug='astk17-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)
        self.users = {}
        for nom in REFUSES + ('Administrateur',):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms[nom]),
                est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'astk17-{nom.lower().replace(" ", "-")}',
                password='x', company=self.company, role=role)
        self.legacy = User.objects.create_user(
            username='astk17-legacy', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK17',
            telephone='0612345678', email='f@exemple.ma')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK17', sku='ASTK17-1',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1000'))
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK17-1',
            fournisseur=self.fournisseur, note='origine',
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.produit, quantite=2,
            prix_achat_unitaire=Decimal('1000'))
        self.modele = ModeleBonCommandeFournisseur.objects.create(
            company=self.company, nom='Modèle ASTK17',
            fournisseur=self.fournisseur)
        self.modele.lignes.create(produit=self.produit, quantite=3)

    def _corps_creation(self):
        return {'fournisseur': self.fournisseur.id, 'lignes': [{
            'produit': self.produit.id, 'quantite': 1,
            'prix_achat_unitaire': '1000'}]}

    def _gestes(self, api):
        pk = self.bc.pk
        return {
            'create': api.post(BCF, self._corps_creation(), format='json'),
            'create_achats': api.post(BCF_ACHATS, self._corps_creation(),
                                      format='json'),
            'patch': api.patch(f'{BCF}{pk}/', {'note': 'pirate'},
                               format='json'),
            'envoyer': api.post(f'{BCF}{pk}/envoyer/', {}, format='json'),
            'reviser': api.post(f'{BCF}{pk}/reviser/', {}, format='json'),
            'annuler': api.post(f'{BCF}{pk}/annuler/', {}, format='json'),
            'rouvrir': api.post(f'{BCF}{pk}/rouvrir/', {}, format='json'),
            'dupliquer': api.post(f'{BCF}{pk}/dupliquer/', {},
                                  format='json'),
            'fusionner': api.post(f'{BCF}fusionner/', {'ids': [pk]},
                                  format='json'),
            'whatsapp': api.post(f'{BCF}{pk}/whatsapp/', {}, format='json'),
            'envoyer_email': api.post(f'{BCF}{pk}/envoyer-email/', {},
                                      format='json'),
            'modele_create': api.post(MODELES, {
                'nom': 'X', 'fournisseur': self.fournisseur.id,
                'lignes': []}, format='json'),
            'generer': api.post(f'{MODELES}{self.modele.pk}/generer/', {},
                                format='json'),
        }

    def test_commercial_403_creation(self):
        avant = BonCommandeFournisseur.objects.count()
        rep = _api(self.users['Commercial']).post(
            BCF, self._corps_creation(), format='json')
        self.assertEqual(rep.status_code, 403, rep.data)
        self.assertEqual(BonCommandeFournisseur.objects.count(), avant)

    def test_roles_sans_code_403_sur_chaque_geste(self):
        for nom in REFUSES:
            avant = BonCommandeFournisseur.objects.count()
            for geste, rep in self._gestes(_api(self.users[nom])).items():
                with self.subTest(role=nom, geste=geste):
                    self.assertEqual(rep.status_code, 403, rep.data)
            # CLAUSE PERSISTANCE : aucun BCF créé, BCF relu inchangé.
            self.assertEqual(BonCommandeFournisseur.objects.count(), avant)
            self.bc.refresh_from_db()
            self.assertEqual(self.bc.note, 'origine')
            self.assertEqual(self.bc.statut,
                             BonCommandeFournisseur.Statut.BROUILLON)

    def test_administrateur_et_legacy_passent(self):
        for user in (self.users['Administrateur'], self.legacy):
            with self.subTest(user=user.username):
                api = _api(user)
                rep = api.post(BCF, self._corps_creation(), format='json')
                self.assertEqual(rep.status_code, 201, rep.data)
                rep = api.patch(f'{BCF}{self.bc.pk}/', {'note': 'ok'},
                                format='json')
                self.assertEqual(rep.status_code, 200, rep.data)
                rep = api.post(f'{MODELES}{self.modele.pk}/generer/', {},
                               format='json')
                self.assertEqual(rep.status_code, 201, rep.data)
