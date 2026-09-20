"""Tests NTPRT36 — export « mes données » (portabilité, loi 09-08), portail
CLIENT.

Couvre le critère d'acceptation : l'export ne contient STRICTEMENT que les
enregistrements où ``client_id`` == celui du compte demandeur — jamais un
devis/une facture/un ticket d'un autre client, même de la même société.

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt36_export_mes_donnees -v2
"""
import io
import itertools
import json
import zipfile
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.models import DemandeTicketPortail
from apps.portail.services import provisionner_compte_portail_client
from apps.ventes.models import Devis, Facture
from authentication.models import Company

_seq = itertools.count(1)

URL = '/api/django/portail/client/mes-donnees/export/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT36-{n}',
        email=f'ntprt36-{company.id}-{n}@example.invalid')


def make_admin(company):
    client = make_client_crm(company)
    admin, _ = provisionner_compte_portail_client(company, client.id)
    admin.must_change_password = False
    admin.save(update_fields=['must_change_password'])
    return client, admin


def make_devis(company, client, statut=Devis.Statut.ENVOYE):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-NTPRT36-{n}', client=client,
        statut=statut, taux_tva=Decimal('20'))


def make_facture(company, client, statut=Facture.Statut.EMISE):
    n = next(_seq)
    return Facture.objects.create(
        company=company, reference=f'FAC-NTPRT36-{n}', client=client,
        statut=statut, montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
        montant_ttc=Decimal('1200'), taux_tva=Decimal('20'))


def make_demande(company, client, sujet='Panne'):
    return DemandeTicketPortail.objects.create(
        company=company, client=client, sujet=sujet,
        statut=DemandeTicketPortail.Statut.SOUMISE)


class ExportMesDonneesTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt36-co', 'NTPRT36 Société')
        self.client_crm, self.admin = make_admin(self.company)
        self.autre_client = make_client_crm(self.company)
        self.devis = make_devis(self.company, self.client_crm)
        self.devis_autrui = make_devis(self.company, self.autre_client)
        self.facture = make_facture(self.company, self.client_crm)
        self.facture_autrui = make_facture(self.company, self.autre_client)
        self.demande = make_demande(self.company, self.client_crm)
        self.demande_autrui = make_demande(self.company, self.autre_client)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def _lire_json(self, archive, nom):
        return json.loads(archive.read(nom).decode('utf-8'))

    def test_export_est_un_zip_avec_les_trois_json(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(io.BytesIO(res.content))
        noms = archive.namelist()
        for attendu in ('devis.json', 'factures.json', 'tickets.json',
                        'manifest.json'):
            self.assertIn(attendu, noms)

    def test_devis_ne_contient_que_ceux_du_client_connecte(self):
        res = self.api.get(URL)
        archive = zipfile.ZipFile(io.BytesIO(res.content))
        devis = self._lire_json(archive, 'devis.json')
        refs = [d['reference'] for d in devis]
        self.assertIn(self.devis.reference, refs)
        self.assertNotIn(self.devis_autrui.reference, refs)

    def test_factures_ne_contient_que_celles_du_client_connecte(self):
        res = self.api.get(URL)
        archive = zipfile.ZipFile(io.BytesIO(res.content))
        factures = self._lire_json(archive, 'factures.json')
        refs = [f['reference'] for f in factures]
        self.assertIn(self.facture.reference, refs)
        self.assertNotIn(self.facture_autrui.reference, refs)

    def test_tickets_ne_contient_que_ceux_du_client_connecte(self):
        res = self.api.get(URL)
        archive = zipfile.ZipFile(io.BytesIO(res.content))
        tickets = self._lire_json(archive, 'tickets.json')
        sujets = [t['sujet'] for t in tickets]
        self.assertEqual(sujets, [self.demande.sujet])

    def test_manifest_porte_le_client_id_du_compte_demandeur(self):
        res = self.api.get(URL)
        archive = zipfile.ZipFile(io.BytesIO(res.content))
        manifeste = self._lire_json(archive, 'manifest.json')
        self.assertEqual(manifeste['client_id'], self.client_crm.id)

    def test_un_membre_dune_autre_societe_est_refuse(self):
        autre = make_company('ntprt36-co-b', 'NTPRT36 Société B')
        _, autre_admin = make_admin(autre)
        api = APIClient()
        api.force_authenticate(user=autre_admin)
        res = api.get(URL)
        self.assertEqual(res.status_code, 200)
        archive = zipfile.ZipFile(io.BytesIO(res.content))
        devis = self._lire_json(archive, 'devis.json')
        self.assertEqual(devis, [])
