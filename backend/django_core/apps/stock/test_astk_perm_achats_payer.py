"""ASTK19 (D-ASTK-3) — les gestes « payer » exigent ``achats_payer``.

Rejoue TEN-9 (audit stock 06/10/2026) : comA_paiement=201, techA_paiement=201,
trespA_paiement=201 (nb_paiements=3). Désormais seuls Directeur et
Administrateur (porteurs du code depuis ASTK16) règlent un fournisseur ;
légacy responsable/admin inchangé.

Source réelle : rôles canoniques ``CANONICAL_SYSTEM_ROLES``,
``HasPermissionOrLegacy`` ; aucun mock.

Run :
    python manage.py test apps.stock.test_astk_perm_achats_payer -v 2
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
    AcompteFournisseur, AvoirFournisseur, FactureFournisseur, Fournisseur,
    PaiementFournisseur,
)
from authentication.models import Company

User = get_user_model()

ACHATS = '/api/django/achats/'
STOCK = '/api/django/stock/'
REFUSES = ('Commercial', 'Technicien', 'Technicien responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PermAchatsPayerTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK19', slug='astk19-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)
        self.users = {}
        for nom in REFUSES + ('Administrateur', 'Directeur'):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms[nom]),
                est_systeme=True)
            self.users[nom] = User.objects.create_user(
                username=f'astk19-{nom.lower().replace(" ", "-")}',
                password='x', company=self.company, role=role)
        self.legacy = User.objects.create_user(
            username='astk19-legacy', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK19')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-T9',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ht=Decimal('1000'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('1000'))

    def _corps_paiement(self):
        return {'facture': self.facture.pk, 'montant': '100',
                'mode': 'virement', 'date_paiement': '2026-09-10'}

    def test_commercial_403_paiement(self):
        rep = _api(self.users['Commercial']).post(
            f'{ACHATS}paiements-fournisseur/', self._corps_paiement(),
            format='json')
        self.assertEqual(rep.status_code, 403, rep.data)
        self.assertEqual(PaiementFournisseur.objects.count(), 0)

    def test_roles_sans_code_403_sur_chaque_geste(self):
        statut_avant = self.facture.statut
        nb_acomptes = AcompteFournisseur.objects.count()
        nb_avoirs = AvoirFournisseur.objects.count()
        fid = self.facture.pk
        for nom in REFUSES:
            api = _api(self.users[nom])
            reps = {
                'paiement_achats': api.post(
                    f'{ACHATS}paiements-fournisseur/',
                    self._corps_paiement(), format='json'),
                'paiement_stock': api.post(
                    f'{STOCK}paiements-fournisseur/',
                    self._corps_paiement(), format='json'),
                'facture_paiements': api.post(
                    f'{STOCK}factures-fournisseur/{fid}/paiements/',
                    {'montant': '100'}, format='json'),
                'facture_patch': api.patch(
                    f'{STOCK}factures-fournisseur/{fid}/',
                    {'notes': 'x'}, format='json'),
                'resoudre_exception': api.post(
                    f'{STOCK}factures-fournisseur/{fid}/resoudre-exception/',
                    {}, format='json'),
                'reception_facturer': api.post(
                    f'{STOCK}receptions-fournisseur/999999/facturer/', {},
                    format='json'),
                'bcf_facturer': api.post(
                    f'{STOCK}bons-commande-fournisseur/999999/facturer/', {},
                    format='json'),
                'acompte': api.post(
                    f'{STOCK}acomptes-fournisseur/', {
                        'fournisseur': self.fournisseur.pk,
                        'montant': '100'}, format='json'),
                'avoir_create': api.post(
                    f'{STOCK}avoirs-fournisseur/', {
                        'fournisseur': self.fournisseur.pk}, format='json'),
                'avoir_imputer': api.post(
                    f'{STOCK}avoirs-fournisseur/999999/imputer/', {},
                    format='json'),
                'retour_generer_avoir': api.post(
                    f'{STOCK}retours-fournisseur/999999/generer-avoir/', {},
                    format='json'),
            }
            for geste, rep in reps.items():
                with self.subTest(role=nom, geste=geste):
                    self.assertEqual(rep.status_code, 403, rep.data)
        # CLAUSE PERSISTANCE : aucun paiement, statut de facture inchangé.
        self.assertEqual(PaiementFournisseur.objects.count(), 0)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, statut_avant)
        self.assertEqual(AcompteFournisseur.objects.count(), nb_acomptes)
        self.assertEqual(AvoirFournisseur.objects.count(), nb_avoirs)

    def test_administrateur_directeur_et_legacy_paient(self):
        users = [self.users['Administrateur'], self.users['Directeur'],
                 self.legacy]
        for i, user in enumerate(users, start=1):
            with self.subTest(user=user.username):
                rep = _api(user).post(
                    f'{ACHATS}paiements-fournisseur/',
                    self._corps_paiement(), format='json')
                self.assertEqual(rep.status_code, 201, rep.data)
                self.assertEqual(PaiementFournisseur.objects.count(), i)

    def test_lecture_paiements_par_code(self):
        # Survivant unique de la lecture : achats_payer OU prix_achat_voir.
        url = f'{STOCK}paiements-fournisseur/'
        self.assertEqual(
            _api(self.users['Administrateur']).get(url).status_code, 200)
        self.assertEqual(_api(self.legacy).get(url).status_code, 200)
        self.assertEqual(
            _api(self.users['Commercial']).get(url).status_code, 403)
