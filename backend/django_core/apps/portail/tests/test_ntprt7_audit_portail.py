"""NTPRT7 — Audit des accès portail : les 4 actions client réellement
atteignables depuis le portail (login excepté — hors périmètre de cette
lane, câblé dans ``authentication/views.py``) écrivent bien dans
``audit.AuditLog`` avec ``via_portail=True``, sans dupliquer le modèle
d'audit.

Couvre : acceptation de devis, paiement (intention), ouverture de ticket SAV,
téléchargement d'un document (photo de preuve de livraison).

Run :
    python manage.py test apps.portail.tests.test_ntprt7_audit_portail -v2
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.crm.models import Client
from apps.facturation.models import Facture
from apps.installations.models import Installation, Livraison
from apps.installations.models_pod import PreuveLivraison
from apps.records.models import Attachment
from apps.roles.models import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT7-{n}',
        email=f'ntprt7-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, client_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = client_id
    user.save()
    return user


class AccepterDevisAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt7-devis-a', 'NTPRT7 Devis A')
        self.client_crm = make_client_crm(self.company)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-NTPRT7-1',
            client=self.client_crm, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.user = make_portal_user(
            self.company, 'ntprt7-devis-user', self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_acceptation_devis_journalisee_via_portail(self):
        res = self.api.post(
            f'/api/django/portail/mes-devis/{self.devis.id}/accepter/',
            {'nom': 'Client NTPRT7', 'consent_esign': True}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

        entry = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.ACCEPT).latest('id')
        self.assertTrue(entry.via_portail)
        self.assertEqual(entry.user_id, self.user.id)


class PayerFactureAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt7-facture-a', 'NTPRT7 Facture A')
        self.client_crm = make_client_crm(self.company)
        montant_ttc = Decimal('12000')
        montant_ht = (montant_ttc / Decimal('1.2')).quantize(Decimal('0.01'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-NTPRT7-1',
            client=self.client_crm, statut=Facture.Statut.EMISE,
            montant_ht=montant_ht, montant_tva=montant_ttc - montant_ht,
            montant_ttc=montant_ttc, taux_tva=Decimal('20'))
        self.user = make_portal_user(
            self.company, 'ntprt7-facture-user', self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_paiement_journalise_via_portail(self):
        res = self.api.post(
            f'/api/django/portail/mes-factures/{self.facture.id}/payer/',
            {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

        entry = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.PAYMENT).latest('id')
        self.assertTrue(entry.via_portail)
        self.assertEqual(entry.user_id, self.user.id)


class OuvrirTicketAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt7-ticket-a', 'NTPRT7 Ticket A')
        self.client_crm = make_client_crm(self.company)
        self.user = make_portal_user(
            self.company, 'ntprt7-ticket-user', self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_ouverture_ticket_journalisee_via_portail(self):
        res = self.api.post(
            '/api/django/portail/mes-demandes-sav/',
            {'sujet': 'Onduleur en défaut'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)

        entry = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.CREATE,
            via_portail=True).latest('id')
        self.assertEqual(entry.user_id, self.user.id)


class TelechargementDocAuditTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt7-doc-a', 'NTPRT7 Doc A')
        self.client_crm = make_client_crm(self.company)
        self.installation = Installation.objects.create(
            company=self.company, client=self.client_crm,
            reference=f'CH-NTPRT7-{next(_seq)}')
        self.livraison = Livraison.objects.create(
            company=self.company, installation=self.installation,
            reference='LIV-NTPRT7-A')
        self.attachment = Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Livraison),
            object_id=self.livraison.id,
            file_key='attachments/ntprt7.jpg',
            filename='preuve.jpg', size=10, mime='image/jpeg')
        self.pod = PreuveLivraison.objects.create(
            company=self.company, livraison=self.livraison,
            signataire_nom='Client NTPRT7', photo=self.attachment)
        self.user = make_portal_user(
            self.company, 'ntprt7-doc-user', self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_telechargement_photo_preuve_journalise_via_portail(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'\xff\xd8\xff', None)):
            res = self.api.get(
                '/api/django/portail/mes-livraisons/'
                f'{self.livraison.id}/preuve-photo/')
        self.assertEqual(res.status_code, 200)

        entry = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.EXPORT,
            via_portail=True).latest('id')
        self.assertEqual(entry.user_id, self.user.id)
