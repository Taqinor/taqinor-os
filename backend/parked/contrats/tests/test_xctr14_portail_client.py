"""Tests XCTR14 — Portail client : « Mes contrats & abonnements ».

Couvre : un client ne voit QUE ses propres contrats (isolation cross-tenant +
cross-client), les demandes 1-clic (renouvellement/résiliation) créent une
activité côté ERP SANS jamais modifier le statut du contrat, un token invalide
renvoie 404 sans fuite.
"""
import secrets

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.contrats.models import Contrat, ContratActivity
from apps.contrats import services
from apps.crm.models import Client
from apps.compta.models import ComptePortailClient


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom):
    return Client.objects.create(company=company, nom=nom)


def make_compte_portail(company, client):
    return ComptePortailClient.objects.create(
        company=company, client=client,
        token_acces=secrets.token_urlsafe(32))


def make_contrat(company, client_id, **kwargs):
    return Contrat.objects.create(
        company=company, client_id=client_id,
        objet=kwargs.pop('objet', 'Contrat O&M'), **kwargs)


class PortailContratsTests(TestCase):
    BASE = '/api/django/public/contrats/portail/'

    def setUp(self):
        self.co_a = make_company('xctr14-a', 'A')
        self.co_b = make_company('xctr14-b', 'B')
        self.client_a1 = make_client(self.co_a, 'Client A1')
        self.client_a2 = make_client(self.co_a, 'Client A2')
        self.client_b1 = make_client(self.co_b, 'Client B1')
        self.compte_a1 = make_compte_portail(self.co_a, self.client_a1)
        self.compte_b1 = make_compte_portail(self.co_b, self.client_b1)
        self.api = APIClient()

    def test_client_voit_uniquement_ses_contrats(self):
        make_contrat(self.co_a, self.client_a1.id, objet='Contrat A1-1')
        make_contrat(self.co_a, self.client_a2.id, objet='Contrat A2-1')
        make_contrat(self.co_b, self.client_b1.id, objet='Contrat B1-1')

        resp = self.api.get(f'{self.BASE}{self.compte_a1.token_acces}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        objets = {r['objet'] for r in resp.data['results']}
        self.assertEqual(objets, {'Contrat A1-1'})

    def test_token_invalide_404_sans_fuite(self):
        resp = self.api.get(f'{self.BASE}bogus-token-xyz/')
        self.assertEqual(resp.status_code, 404)

    def test_token_compte_inactif_404(self):
        self.compte_a1.actif = False
        self.compte_a1.save(update_fields=['actif'])
        make_contrat(self.co_a, self.client_a1.id)
        resp = self.api.get(f'{self.BASE}{self.compte_a1.token_acces}/')
        self.assertEqual(resp.status_code, 404)

    def test_demande_renouvellement_cree_activite_sans_changer_statut(self):
        contrat = make_contrat(
            self.co_a, self.client_a1.id, statut=Contrat.Statut.ACTIF)
        url = (f'{self.BASE}{self.compte_a1.token_acces}/'
               f'{contrat.id}/demande/')
        resp = self.api.post(
            url, {'type': 'renouvellement', 'message': 'SVP'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

        activite = ContratActivity.objects.get(contrat=contrat)
        self.assertIn('renouvellement', activite.message.lower())
        self.assertEqual(activite.type, ContratActivity.Kind.NOTE)

    def test_demande_resiliation_cree_activite(self):
        contrat = make_contrat(
            self.co_a, self.client_a1.id, statut=Contrat.Statut.ACTIF)
        url = (f'{self.BASE}{self.compte_a1.token_acces}/'
               f'{contrat.id}/demande/')
        resp = self.api.post(url, {'type': 'resiliation'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            ContratActivity.objects.filter(
                contrat=contrat,
                message__icontains='résiliation').exists())

    def test_demande_type_invalide_400(self):
        contrat = make_contrat(self.co_a, self.client_a1.id)
        url = (f'{self.BASE}{self.compte_a1.token_acces}/'
               f'{contrat.id}/demande/')
        resp = self.api.post(url, {'type': 'autre_chose'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_demande_contrat_autre_client_404(self):
        """Un client A1 ne peut pas demander sur un contrat d'un autre client
        (même société) — pas de fuite cross-client."""
        contrat_autre = make_contrat(self.co_a, self.client_a2.id)
        url = (f'{self.BASE}{self.compte_a1.token_acces}/'
               f'{contrat_autre.id}/demande/')
        resp = self.api.post(url, {'type': 'renouvellement'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_demande_contrat_autre_societe_404(self):
        contrat_b = make_contrat(self.co_b, self.client_b1.id)
        url = (f'{self.BASE}{self.compte_a1.token_acces}/'
               f'{contrat_b.id}/demande/')
        resp = self.api.post(url, {'type': 'renouvellement'}, format='json')
        self.assertEqual(resp.status_code, 404)


class DemanderActionPortailServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr14-svc', 'Svc')
        self.client_obj = make_client(self.company, 'Client Svc')
        self.contrat = make_contrat(self.company, self.client_obj.id)

    def test_type_invalide_leve_erreur(self):
        with self.assertRaises(services.DemandePortailError):
            services.demander_action_portail(
                self.contrat, type_demande='invalide')

    def test_statut_inchange(self):
        ancien = self.contrat.statut
        services.demander_action_portail(
            self.contrat, type_demande='renouvellement')
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, ancien)
