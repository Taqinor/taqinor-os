"""ASEC28 (C-ASEC-005 site (a), C-ASEC-009 volet mandat) — FK inscriptibles
du bon de commande (`client`, `devis`, `lead`), du mandat de paiement
(`client`), du paramétrage de relance (`client`, `responsable`) et de la
remise d'encaissement (`technicien`) bornées à la société ;
`MandatPaiement.statut`/`consentement_horodate` en lecture seule ;
`mandat_actif_pour_client` filtré par la société du client.

Rouge sur 51f22174f (V5 : 200/201 ; mandat révoqué → actif par PATCH).
Endpoints et service réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_xfac_asec28_bc_mandat_fk"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class BcMandatRelanceRemiseTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client, Lead
        from apps.ventes.models import (
            BonCommande, Devis, MandatPaiement, ParametrageRelanceClient,
            RemiseEncaissement,
        )
        from authentication.models import Company

        self.a = Company.objects.create(nom='ASEC28 A', slug='asec28-a')
        self.b = Company.objects.create(nom='ASEC28 B', slug='asec28-b')
        self.user = User.objects.create_user(
            username='asec28_resp', password='x', role_legacy='responsable',
            company=self.a)
        self.user_b = User.objects.create_user(
            username='asec28_resp_b', password='x',
            role_legacy='responsable', company=self.b)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        def _client(company, suffixe):
            return Client.objects.create(
                company=company, nom=f'Client {suffixe}', prenom='X',
                email=f'asec28-{suffixe}@example.invalid')

        self.client_a = _client(self.a, 'A')
        self.client_b = _client(self.b, 'B')
        self.devis_b = Devis.objects.create(
            company=self.b, reference='DEV-ASEC28-B', client=self.client_b,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'))
        self.lead_b = Lead.objects.create(company=self.b, nom='Lead',
                                          prenom='B')
        self.bc = BonCommande.objects.create(
            company=self.a, reference='BC-ASEC28-A', client=self.client_a,
            statut=BonCommande.Statut.EN_ATTENTE)
        self.mandat = MandatPaiement.objects.create(
            company=self.a, client=self.client_a, provider='mock_tokenized',
            token='TOK-A', statut=MandatPaiement.Statut.REVOQUE)
        self.relance = ParametrageRelanceClient.objects.create(
            company=self.a, client=self.client_a, responsable=self.user)
        self.remise = RemiseEncaissement.objects.create(
            company=self.a, technicien=self.user, reference='REM-ASEC28-1',
            date_collecte=date.today(), montant_declare=Decimal('10.00'))

    def test_bc_fk_etrangere_400(self):
        url = f'/api/django/ventes/bons-commande/{self.bc.id}/'
        for champ, valeur in (('client', self.client_b.pk),
                              ('devis', self.devis_b.pk),
                              ('lead', self.lead_b.pk)):
            with self.subTest(champ=champ):
                r = self.api.patch(url, {champ: valeur}, format='json')
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn(champ, r.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.client_id, self.client_a.pk)
        self.assertIsNone(self.bc.devis_id)
        self.assertIsNone(self.bc.lead_id)

    def test_mandat_client_etranger_400(self):
        url = f'/api/django/ventes/mandats-paiement/{self.mandat.id}/'
        r = self.api.patch(url, {'client': self.client_b.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.post('/api/django/ventes/mandats-paiement/',
                          {'client': self.client_b.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.mandat.refresh_from_db()
        self.assertEqual(self.mandat.client_id, self.client_a.pk)

    def test_mandat_revoque_reste_revoque(self):
        from apps.ventes.models import MandatPaiement
        url = f'/api/django/ventes/mandats-paiement/{self.mandat.id}/'
        r = self.api.patch(url, {'statut': 'actif',
                                 'consentement_horodate':
                                     '2026-10-01T10:00:00Z'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.mandat.refresh_from_db()
        self.assertEqual(self.mandat.statut, MandatPaiement.Statut.REVOQUE)
        self.assertIsNone(self.mandat.consentement_horodate)

    def test_relance_responsable_etranger_400(self):
        url = (f'/api/django/ventes/parametrages-relance-client/'
               f'{self.relance.id}/')
        for champ, valeur in (('responsable', self.user_b.pk),
                              ('client', self.client_b.pk)):
            with self.subTest(champ=champ):
                r = self.api.patch(url, {champ: valeur}, format='json')
                self.assertEqual(r.status_code, 400, r.data)
        self.relance.refresh_from_db()
        self.assertEqual(self.relance.responsable_id, self.user.pk)
        self.assertEqual(self.relance.client_id, self.client_a.pk)

    def test_remise_technicien_etranger_400(self):
        url = f'/api/django/ventes/remises-encaissement/{self.remise.id}/'
        r = self.api.patch(url, {'technicien': self.user_b.pk},
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.remise.refresh_from_db()
        self.assertEqual(self.remise.technicien_id, self.user.pk)

    def test_mandat_actif_filtre_societe(self):
        from apps.ventes.domain.encaissements import mandat_actif_pour_client
        from apps.ventes.models import MandatPaiement
        # Construction de test : un mandat ACTIF de B porte le client de A.
        etranger = MandatPaiement.objects.create(
            company=self.b, client=self.client_a, provider='mock_tokenized',
            token='TOK-B', statut=MandatPaiement.Statut.ACTIF)
        self.assertIsNone(mandat_actif_pour_client(self.client_a))
        propre = MandatPaiement.objects.create(
            company=self.a, client=self.client_a, provider='mock_tokenized',
            token='TOK-A2', statut=MandatPaiement.Statut.ACTIF)
        self.assertEqual(mandat_actif_pour_client(self.client_a), propre)
        self.assertNotEqual(mandat_actif_pour_client(self.client_a),
                            etranger)
