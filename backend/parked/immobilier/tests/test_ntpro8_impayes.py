"""NTPRO8 — Encaissements et impayés avec relances dédiées.

Couvre : le tableau des impayés liste les locataires en retard avec montant +
jours de retard (lu via ``apps.ventes.selectors``, mocké), et une relance
incrémente le niveau (1 → 2 → 3, plafonné).
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, EcheanceLoyer, Local, Locataire, Niveau, RelanceLoyer,
    Site,
)
from apps.immobilier.selectors import echeances_impayees
from apps.immobilier.services import creer_bail, generer_echeancier, relancer_echeance

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntpro8ImpayesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-imp-a', 'Immo Imp A')
        self.admin_a = make_user(self.co_a, 'immo-imp-admin-a')
        site = Site.objects.create(company=self.co_a, nom='Résidence')
        batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=batiment, numero='RDC')
        local = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01')
        locataire = Locataire.objects.create(company=self.co_a, nom='Bennani')
        self.bail = creer_bail(
            company=self.co_a, local=local, locataire=locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=1, loyer_mensuel_ht=Decimal('3000.00'))
        generer_echeancier(self.bail)
        self.echeance = EcheanceLoyer.objects.get(bail=self.bail)
        self.echeance.statut = EcheanceLoyer.Statut.EMISE
        self.echeance.facture_ventes_id = 777
        self.echeance.save(update_fields=['statut', 'facture_ventes_id'])

    def test_echeances_impayees_liste_montant_et_jours_retard(self):
        fake_facture = type('F', (), {'reference': 'FAC-0001'})()
        with patch(
            'apps.ventes.selectors.jours_impaye_facture', return_value=15,
        ), patch(
            'apps.ventes.selectors.get_facture_scoped',
            return_value=fake_facture,
        ):
            resultats = echeances_impayees(self.co_a)

        self.assertEqual(len(resultats), 1)
        row = resultats[0]
        self.assertEqual(row['echeance_id'], self.echeance.id)
        self.assertEqual(row['locataire'], 'Bennani')
        self.assertEqual(row['jours_retard'], 15)
        self.assertEqual(row['montant_total'], Decimal('3000.00'))
        self.assertEqual(row['facture_reference'], 'FAC-0001')

    def test_echeance_non_en_retard_absente_de_la_liste(self):
        with patch(
            'apps.ventes.selectors.jours_impaye_facture', return_value=0,
        ), patch('apps.ventes.selectors.get_facture_scoped', return_value=None):
            resultats = echeances_impayees(self.co_a)
        self.assertEqual(resultats, [])

    def test_relance_incremente_le_niveau(self):
        r1 = relancer_echeance(self.echeance)
        self.assertEqual(r1.niveau, 1)
        r2 = relancer_echeance(self.echeance)
        self.assertEqual(r2.niveau, 2)
        r3 = relancer_echeance(self.echeance)
        self.assertEqual(r3.niveau, 3)
        # Plafonné à 3 : une 4e relance reste au niveau 3.
        r4 = relancer_echeance(self.echeance)
        self.assertEqual(r4.niveau, 3)
        self.echeance.refresh_from_db()
        self.assertEqual(self.echeance.statut, EcheanceLoyer.Statut.RELANCEE)
        self.assertEqual(
            RelanceLoyer.objects.filter(echeance_loyer=self.echeance).count(), 4)

    def test_api_impayees_endpoint(self):
        api = auth(self.admin_a)
        with patch(
            'apps.ventes.selectors.jours_impaye_facture', return_value=10,
        ), patch(
            'apps.ventes.selectors.get_facture_scoped', return_value=None,
        ):
            resp = api.get('/api/django/immobilier/echeances-loyer/impayees/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['jours_retard'], 10)

    def test_api_relancer_action(self):
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/immobilier/echeances-loyer/{self.echeance.id}/'
            'relancer/', {'canal': 'email'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['niveau'], 1)
        self.assertEqual(resp.data['canal'], 'email')
