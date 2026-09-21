"""Tests NTPRT38 — recherche globale, version scopée-portail du client
connecté.

Couvre le critère d'acceptation : aucun résultat hors du périmètre du compte
connecté (jamais un devis/une facture/un ticket d'un autre client, même de
la même société). Un mot-clé vide renvoie des groupes vides.

SOLMVP16 — le groupe « documents » (GED partagée, module sorti du produit) a
été retiré ; ce test ne couvre plus que devis/factures/tickets.

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt38_recherche_portail -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.models import DemandeTicketPortail
from apps.portail.services import provisionner_compte_portail_client
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)

URL = '/api/django/portail/client/recherche/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT38-{n}',
        email=f'ntprt38-{company.id}-{n}@example.invalid')


def make_admin(company):
    client = make_client_crm(company)
    admin, _ = provisionner_compte_portail_client(company, client.id)
    admin.must_change_password = False
    admin.save(update_fields=['must_change_password'])
    return client, admin


def make_devis(company, client, reference):
    return Devis.objects.create(
        company=company, reference=reference, client=client,
        statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))


def make_demande(company, client, sujet):
    return DemandeTicketPortail.objects.create(
        company=company, client=client, sujet=sujet,
        statut=DemandeTicketPortail.Statut.SOUMISE)


class RecherchePortailClientTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt38-co', 'NTPRT38 Société')
        self.client_crm, self.admin = make_admin(self.company)
        self.autre_client = make_client_crm(self.company)
        self.devis = make_devis(
            self.company, self.client_crm, 'DEV-NTPRT38-ONDULEUR')
        self.devis_autrui = make_devis(
            self.company, self.autre_client, 'DEV-NTPRT38-AUTRUI')
        self.demande = make_demande(
            self.company, self.client_crm, 'Onduleur en panne')
        self.demande_autrui = make_demande(
            self.company, self.autre_client, 'Onduleur cassé aussi')
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def test_mot_cle_vide_renvoie_des_groupes_vides(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['query'], '')
        for groupe in res.data['groups']:
            self.assertEqual(groupe['results'], [])

    def test_recherche_devis_scopee_au_client_connecte(self):
        res = self.api.get(URL, {'q': 'ONDULEUR'})
        self.assertEqual(res.status_code, 200, res.data)
        groupe_devis = next(
            g for g in res.data['groups'] if g['type'] == 'devis')
        labels = [r['label'] for r in groupe_devis['results']]
        self.assertIn(self.devis.reference, labels)
        self.assertNotIn(self.devis_autrui.reference, labels)

    def test_recherche_ticket_najamais_le_ticket_dun_autre_client(self):
        res = self.api.get(URL, {'q': 'onduleur'})
        groupe_ticket = next(
            g for g in res.data['groups'] if g['type'] == 'ticket')
        labels = [r['label'] for r in groupe_ticket['results']]
        self.assertIn(self.demande.sujet, labels)
        self.assertNotIn(self.demande_autrui.sujet, labels)

    def test_un_compte_dune_autre_societe_ne_voit_rien(self):
        autre = make_company('ntprt38-co-b', 'NTPRT38 Société B')
        _, autre_admin = make_admin(autre)
        api = APIClient()
        api.force_authenticate(user=autre_admin)
        res = api.get(URL, {'q': 'onduleur'})
        groupe_devis = next(
            g for g in res.data['groups'] if g['type'] == 'devis')
        self.assertEqual(groupe_devis['results'], [])
