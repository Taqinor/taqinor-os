"""ACRM7 (C-ACRM-004) — l'objet SECONDAIRE d'une action de détail est résolu
dans la PORTÉE de l'appelant.

Sonde V_VA LVIEW1-4 : (a) « convertir-client » liait un client d'un collègue
hors portée (200) ; (b) « locataire » reliait le propriétaire connu d'un
collègue (``proprietaire_relie`` + une note dans SON chatter) ; (c)
« relancer-dormance » posait la note sur le lead le plus récent du client,
celui d'un collègue. D-ACRM-1 (recommandation appliquée par défaut) : un
objet hors portée est traité comme ABSENT.

Rôles réels (Commercial, portée équipe sans superviseur = lui-même) ; aucun
mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead, LeadActivity
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

User = get_user_model()
LEADS = '/api/django/crm/leads/'
CLIENTS = '/api/django/crm/clients/'
TEL = '+212661707070'


class ObjetSecondairePorteeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM7 Solaire', slug='acrm7-portee')
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        self.moi = User.objects.create_user(
            username='acrm7-moi', password='x', company=self.company,
            role=role)
        self.collegue = User.objects.create_user(
            username='acrm7-collegue', password='x', company=self.company,
            role=role)
        self.lead = Lead.objects.create(
            company=self.company, nom='Mon', prenom='Lead', owner=self.moi,
            telephone='+212661707071')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.moi)}'))

    def test_lier_client_hors_portee_refuse(self):
        cli_h = Client.objects.create(
            company=self.company, nom='SondeClientHors')
        Lead.objects.create(company=self.company, nom='Collegue',
                            owner=self.collegue, client=cli_h)
        self.assertEqual(
            self.api.get(f'{CLIENTS}{cli_h.pk}/').status_code, 404)
        hors = self.api.post(f'{LEADS}{self.lead.pk}/convertir-client/',
                             {'mode': 'lier', 'client_id': cli_h.pk},
                             format='json')
        absent = self.api.post(f'{LEADS}{self.lead.pk}/convertir-client/',
                               {'mode': 'lier', 'client_id': 99999999},
                               format='json')
        self.assertEqual(hors.status_code, 400)
        self.assertEqual(hors.data['client_id'], ['Client introuvable.'])
        self.assertEqual(absent.status_code, 400)
        # Enveloppe YAPIC3 identique, au ``request_id`` (par requête) près.
        hors_err = {k: v for k, v in hors.data['error'].items()
                    if k != 'request_id'}
        absent_err = {k: v for k, v in absent.data['error'].items()
                      if k != 'request_id'}
        self.assertEqual(hors_err, absent_err)
        self.assertEqual(set(hors.data), set(absent.data))
        self.assertEqual(hors.data['client_id'], absent.data['client_id'])
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.client_id)

    def test_locataire_proprio_hors_portee_traite_absent(self):
        lp = Lead.objects.create(
            company=self.company, nom='ProprioCollegue', prenom='Lp',
            owner=self.collegue, telephone=TEL)
        avant = LeadActivity.objects.filter(lead=lp).count()
        resp = self.api.post(
            f'{LEADS}{self.lead.pk}/locataire/',
            {'proprietaire': {'nom': 'Proprio', 'telephone': TEL}},
            format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        self.assertNotEqual(resp.data['issue'], 'proprietaire_relie')
        self.assertNotEqual(resp.data['lead_proprietaire']['id'], lp.pk)
        self.assertNotIn('ProprioCollegue', resp.content.decode())
        self.assertEqual(LeadActivity.objects.filter(lead=lp).count(), avant)

    def test_relancer_dormance_lead_en_portee(self):
        mixte = Client.objects.create(company=self.company, nom='Mixte')
        mien = Lead.objects.create(company=self.company, nom='MixteMoi',
                                   owner=self.moi, client=mixte)
        sien = Lead.objects.create(company=self.company, nom='MixteCollegue',
                                   owner=self.collegue, client=mixte)
        Lead.objects.filter(pk=sien.pk).update(
            date_creation=timezone.now() + datetime.timedelta(days=1))
        avant_sien = LeadActivity.objects.filter(lead=sien).count()
        avant_mien = LeadActivity.objects.filter(lead=mien).count()
        resp = self.api.post(f'{CLIENTS}{mixte.pk}/relancer-dormance/')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(LeadActivity.objects.filter(lead=sien).count(),
                         avant_sien)
        self.assertEqual(LeadActivity.objects.filter(lead=mien).count(),
                         avant_mien + 1)
