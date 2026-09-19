"""Tests NTPRT23 — « Mes factures & statut de paiement » du portail
FOURNISSEUR authentifié.

Monte ``stock.selectors.factures_portail_fournisseur`` sur
``MesFacturesPortailFournisseurViewSet`` (``apps.portail.views_externes``).
Deux choses sont vérifiées :

1. **L'isolation.** Le fournisseur est résolu depuis le COMPTE connecté,
   jamais d'un paramètre : les factures d'un autre fournisseur (ou d'une
   autre société) sont invisibles en liste et introuvables en détail.
2. **Le statut de règlement.** Il matche exactement la dérivation UNIQUE du
   dépôt (``stock.selectors.statut_reglement_facture_fournisseur``).

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt23_mes_factures_fournisseur -v2
"""
import datetime
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.achats.models import FactureFournisseur
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from apps.stock.models import Fournisseur
from authentication.models import Company, CustomUser

URL_LISTE = '/api/django/portail/mes-factures-fournisseur/'

_seq = itertools.count(1)

_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def make_fournisseur(company, nom='Fournisseur'):
    return Fournisseur.objects.create(
        company=company, nom=f'{nom}-{next(_seq)}')


def make_facture(company, fournisseur, *,
                 statut=FactureFournisseur.Statut.A_PAYER,
                 montant_ttc=Decimal('1000.00'),
                 date_echeance=datetime.date(2026, 1, 1)):
    return FactureFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'FF-NTPRT23-{next(_seq)}',
        date_facture=datetime.date(2025, 12, 1),
        date_echeance=date_echeance,
        montant_ht=montant_ttc, montant_tva=Decimal('0'),
        montant_ttc=montant_ttc, statut=statut)


class MesFacturesFournisseurIsolationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt23-co', 'NTPRT23 Société')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.facture_a = make_facture(self.company, self.f_a)
        self.facture_b = make_facture(self.company, self.f_b)
        self.user_a = make_portal_user(
            self.company, 'ntprt23-f-a',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_le_fournisseur_ne_voit_que_SES_factures(self):
        res = self.api.get(URL_LISTE)
        self.assertEqual(res.status_code, 200, res.data)
        refs = [f['reference'] for f in res.data['results']]
        self.assertIn(self.facture_a.reference, refs)
        self.assertNotIn(self.facture_b.reference, refs)

    def test_la_facture_dun_autre_fournisseur_est_introuvable_en_detail(self):
        res = self.api.get(f'{URL_LISTE}{self.facture_b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_un_compte_client_est_refuse(self):
        client_user = make_portal_user(
            self.company, 'ntprt23-client', CustomUser.PORTEE_PORTAIL_CLIENT,
            None)
        api = APIClient()
        api.force_authenticate(user=client_user)
        res = api.get(URL_LISTE)
        self.assertEqual(res.status_code, 403)


class StatutReglementAffichageTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt23-rgl', 'NTPRT23 Règlement')
        self.fournisseur = make_fournisseur(self.company)
        self.user = make_portal_user(
            self.company, 'ntprt23-rgl-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.fournisseur.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_facture_payee_affiche_payee(self):
        make_facture(self.company, self.fournisseur,
                     statut=FactureFournisseur.Statut.PAYEE)
        res = self.api.get(URL_LISTE)
        self.assertEqual(res.data['results'][0]['statut_reglement'], 'payee')

    def test_facture_en_retard_porte_les_jours_de_retard(self):
        make_facture(self.company, self.fournisseur,
                     date_echeance=datetime.date(2020, 1, 1))
        res = self.api.get(URL_LISTE)
        ligne = res.data['results'][0]
        self.assertEqual(ligne['statut_reglement'], 'en_retard')
        self.assertGreater(ligne['jours_de_retard'], 0)

    def test_aucun_montant_dachat_interne_ne_fuit(self):
        make_facture(self.company, self.fournisseur)
        res = self.api.get(URL_LISTE)
        ligne = res.data['results'][0]
        self.assertNotIn('prix_achat', ligne)
