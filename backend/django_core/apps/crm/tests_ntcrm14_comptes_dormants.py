"""NTCRM14 — Détection de comptes dormants (selector + endpoint + commande)."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.management.commands.detecter_comptes_dormants import (
    detecter_comptes_dormants,
)
from apps.crm.models import Client, Lead
from apps.crm.selectors import comptes_dormants
from apps.roles.models import Role
from apps.ventes.models import Devis

User = get_user_model()


def _make_devis(company, client, days_ago):
    devis = Devis.objects.create(
        company=company, client=client, reference=f'DV-{client.pk}')
    Devis.objects.filter(pk=devis.pk).update(
        date_creation=timezone.now() - datetime.timedelta(days=days_ago))
    return devis


class ComptesDormantsSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM14', slug='taqinor-ntcrm14')

    def test_client_sans_devis_ni_facture_jamais_dormant(self):
        Client.objects.create(company=self.company, nom='Jamais acheté')
        self.assertEqual(comptes_dormants(self.company, seuil_jours=90), [])

    def test_client_avec_devis_recent_pas_dormant(self):
        client = Client.objects.create(company=self.company, nom='Client actif')
        _make_devis(self.company, client, days_ago=5)
        self.assertEqual(comptes_dormants(self.company, seuil_jours=90), [])

    def test_client_avec_devis_ancien_est_dormant(self):
        client = Client.objects.create(company=self.company, nom='Client froid')
        _make_devis(self.company, client, days_ago=100)
        result = comptes_dormants(self.company, seuil_jours=90)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['client'].pk, client.pk)
        self.assertGreaterEqual(result[0]['jours_inactivite'], 90)

    def test_activite_lead_recente_empeche_la_dormance(self):
        client = Client.objects.create(company=self.company, nom='Client relancé')
        _make_devis(self.company, client, days_ago=200)
        lead = Lead.objects.create(company=self.company, client=client, nom='Lead')
        from apps.crm.models import LeadActivity
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind=LeadActivity.Kind.NOTE,
            body='Appel de suivi récent')
        self.assertEqual(comptes_dormants(self.company, seuil_jours=90), [])


class DetecterComptesDormantsCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM14b', slug='taqinor-ntcrm14b')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.owner = User.objects.create_user(
            username='vendeur_ntcrm14', password='x',
            company=self.company, role=self.role)

    def test_notifie_une_seule_fois_par_dormance(self):
        client = Client.objects.create(company=self.company, nom='Dormant notifié')
        _make_devis(self.company, client, days_ago=120)
        Lead.objects.create(
            company=self.company, client=client, nom='Lead', owner=self.owner)

        nb = detecter_comptes_dormants(seuil_jours=90)
        self.assertEqual(nb, 1)
        client.refresh_from_db()
        self.assertIsNotNone(client.derniere_alerte_dormance)

        # Deuxième passage le même jour : aucune ré-alerte (anti-spam).
        nb2 = detecter_comptes_dormants(seuil_jours=90)
        self.assertEqual(nb2, 0)


class ComptesDormantsEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM14c', slug='taqinor-ntcrm14c')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.user = User.objects.create_user(
            username='vendeur_ntcrm14c', password='x',
            company=self.company, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_endpoint_liste_les_dormants(self):
        client = Client.objects.create(company=self.company, nom='Client dormant API')
        _make_devis(self.company, client, days_ago=95)
        resp = self.api.get('/api/django/crm/clients/dormants/?seuil=90')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['id'], client.pk)
