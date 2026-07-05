"""Tests XFAC26/27 — Portail client self-service : relevé de compte +
contestation de facture.

Couvre :
  * XFAC26 — un client connecté au portail voit son relevé + solde + âge et
    télécharge le PDF ; ne voit JAMAIS les données d'un autre client
    (isolation) ; contenu cohérent avec ``balance_agee``.
  * XFAC27 — une contestation crée la réclamation (litiges), suspend la
    relance de CETTE facture (LITIGE3), notifie/trace ; un client ne peut
    pas contester la facture d'un autre (404) ; token invalide → 404.
"""
import secrets
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.compta.models import ComptePortailClient
from apps.crm.models import Client
from apps.litiges.models import Reclamation
from apps.litiges.selectors import relances_suspendues_pour_facture
from apps.ventes.models import Facture, FactureActivity


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_compte_portail(company, client):
    return ComptePortailClient.objects.create(
        company=company, client=client, token_acces=secrets.token_urlsafe(32))


class _Base(TestCase):
    BASE = '/api/django/compta/portail/'

    def setUp(self):
        self.company = make_company('xfac2627-co', 'XFAC26/27 Co')
        self.autre_company = make_company('xfac2627-autre', 'Autre Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XFAC2627',
            telephone='+212600002627')
        self.autre_client = Client.objects.create(
            company=self.company, nom='Autre', prenom='Client2',
            telephone='+212600002628')
        self.compte = make_compte_portail(self.company, self.client_obj)
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-XFAC2627-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ttc=Decimal('12000'))


class TestReleve(_Base):
    def test_releve_json(self):
        resp = self.client.get(
            f'{self.BASE}{self.compte.token_acces}/mon-releve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('balance_agee', resp.data)
        self.assertIn('solde_courant', resp.data)
        self.assertEqual(len(resp.data['lignes']), 1)
        self.assertEqual(resp.data['lignes'][0]['reference'], self.facture.reference)

    def test_releve_pdf(self):
        resp = self.client.get(
            f'{self.BASE}{self.compte.token_acces}/mon-releve/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_token_invalide_404(self):
        resp = self.client.get(f'{self.BASE}invalidtoken/mon-releve/')
        self.assertEqual(resp.status_code, 404)

    def test_isolation_autre_client(self):
        # Une facture d'un AUTRE client de la MÊME société n'apparaît jamais
        # dans le relevé de ce compte portail.
        Facture.objects.create(
            company=self.company, reference='FAC-XFAC2627-AUTRE',
            client=self.autre_client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ttc=Decimal('5000'))
        resp = self.client.get(
            f'{self.BASE}{self.compte.token_acces}/mon-releve/')
        self.assertEqual(resp.status_code, 200)
        references = [ligne['reference'] for ligne in resp.data['lignes']]
        self.assertNotIn('FAC-XFAC2627-AUTRE', references)

    def test_compte_inactif_404(self):
        self.compte.actif = False
        self.compte.save(update_fields=['actif'])
        resp = self.client.get(
            f'{self.BASE}{self.compte.token_acces}/mon-releve/')
        self.assertEqual(resp.status_code, 404)


class TestContestation(_Base):
    URL = _Base.BASE + '{token}/factures/{facture_id}/contester/'

    def test_contestation_cree_reclamation_et_suspend_relances(self):
        resp = self.client.post(
            self.URL.format(
                token=self.compte.token_acces, facture_id=self.facture.id),
            {'motif': 'montant', 'commentaire': 'Le total ne correspond pas.'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        reclamation_id = resp.data['reclamation_id']

        reclamation = Reclamation.objects.get(id=reclamation_id)
        self.assertEqual(reclamation.company_id, self.company.id)
        self.assertEqual(reclamation.type_reclamation, 'financier')
        self.assertEqual(reclamation.source_type, 'facture')
        self.assertEqual(reclamation.source_id, self.facture.id)
        self.assertTrue(reclamation.bloque_relances)

        self.assertTrue(
            relances_suspendues_pour_facture(self.facture.id, self.company))

        # Trace côté chatter facture.
        self.assertTrue(
            FactureActivity.objects.filter(
                facture=self.facture, field='contestation_portail').exists())

    def test_contestation_facture_autre_client_404(self):
        autre_facture = Facture.objects.create(
            company=self.company, reference='FAC-XFAC2627-0002',
            client=self.autre_client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ttc=Decimal('3000'))
        resp = self.client.post(
            self.URL.format(
                token=self.compte.token_acces, facture_id=autre_facture.id),
            {'motif': 'autre'}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            Reclamation.objects.filter(source_id=autre_facture.id).exists())

    def test_token_invalide_404(self):
        resp = self.client.post(
            self.URL.format(token='invalidtoken', facture_id=self.facture.id),
            {'motif': 'autre'}, format='json')
        self.assertEqual(resp.status_code, 404)
