"""Règle fondateur (08/10/2026) — le RESPONSABLE d'un lead voit TOUJOURS tous
les devis de SON lead, quel qu'en soit l'auteur.

Bug : Reda crée un devis sur un lead dont la responsable est Meriem (rôle
Commercial, portée restreinte « équipe »). La portée de visibilité des devis ne
raisonnait que sur ``created_by`` : le dialogue « Signé » de Meriem
(``GET /ventes/devis/?lead=<id>``) ne listait donc PAS le devis de Reda.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import RESPONSABLE_PERMISSIONS
from apps.ventes.models import Devis

User = get_user_model()
URL = '/api/django/ventes/devis/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids(response):
    data = response.data
    rows = data.get('results', data) if isinstance(data, dict) else data
    return {row['id'] for row in rows}


class TestResponsableLeadVoitTousSesDevis(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='resp-lead-co', defaults={'nom': 'Resp Lead'})[0]
        cls.autre_co = Company.objects.get_or_create(
            slug='resp-lead-autre', defaults={'nom': 'Autre'})[0]
        role_equipe = Role.objects.create(
            company=cls.co, nom='Commercial',
            permissions=RESPONSABLE_PERMISSIONS + ['records_scope_equipe'],
            est_systeme=False)
        # A = auteur du devis (hors portée de B), B = responsable restreinte.
        cls.auteur = User.objects.create_user(
            username='rl_auteur', password='x', role_legacy='responsable',
            company=cls.co)
        cls.meriem = User.objects.create_user(
            username='rl_meriem', password='x', role=role_equipe,
            role_legacy='responsable', company=cls.co)
        cls.client_obj = Client.objects.create(
            company=cls.co, nom='Client', prenom='X',
            email='rl@example.com', telephone='+212600000071',
            adresse='Casablanca')
        cls.lead_meriem = Lead.objects.create(
            company=cls.co, nom='Lead', prenom='Meriem',
            telephone='+212600000072', owner=cls.meriem)
        cls.lead_autre = Lead.objects.create(
            company=cls.co, nom='Lead', prenom='Autre',
            telephone='+212600000073', owner=cls.auteur)
        cls.devis_sur_son_lead = Devis.objects.create(
            company=cls.co, reference='DEV-RL-0001', client=cls.client_obj,
            lead=cls.lead_meriem, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=cls.auteur)
        cls.devis_hors_lead = Devis.objects.create(
            company=cls.co, reference='DEV-RL-0002', client=cls.client_obj,
            lead=cls.lead_autre, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=cls.auteur)
        # Autre société : un devis rattaché (par erreur) au lead de Meriem ne
        # doit JAMAIS fuiter — la société reste bornée en amont.
        autre_client = Client.objects.create(
            company=cls.autre_co, nom='Ext', prenom='Y',
            email='ext@example.com', telephone='+212600000074',
            adresse='Rabat')
        cls.devis_autre_co = Devis.objects.create(
            company=cls.autre_co, reference='DEV-RL-0003',
            client=autre_client, lead=cls.lead_meriem,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'))

    def setUp(self):
        self.api = auth(self.meriem)

    def test_responsable_voit_le_devis_d_un_autre_sur_son_lead(self):
        r = self.api.get(URL, {'lead': self.lead_meriem.id})
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        self.assertEqual(ids(r), {self.devis_sur_son_lead.id})
        r = self.api.get(f'{URL}{self.devis_sur_son_lead.id}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))

    def test_devis_d_autrui_sur_un_lead_non_possede_reste_invisible(self):
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        visibles = ids(r)
        self.assertNotIn(self.devis_hors_lead.id, visibles)
        self.assertNotIn(self.devis_autre_co.id, visibles)
        r = self.api.get(URL, {'lead': self.lead_autre.id})
        self.assertEqual(ids(r), set())
        r = self.api.get(f'{URL}{self.devis_hors_lead.id}/')
        self.assertEqual(r.status_code, 404)

    def test_autre_societe_ne_fuit_jamais(self):
        r = self.api.get(f'{URL}{self.devis_autre_co.id}/')
        self.assertEqual(r.status_code, 404)
