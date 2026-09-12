"""NTDATA18 — fusion supervisée de clients (`crm.services.merge_clients`).

Couvre le critère d'acceptation :
  * après fusion, les DEVIS des doublons pointent le survivant ;
  * les doublons sont NEUTRALISÉS (jamais supprimés) et tracés ;
  * les factures / chantiers / tickets suivent aussi (relations inverses) ;
  * les champs VIDES du survivant sont complétés, jamais écrasés ;
  * une fiche d'une AUTRE société n'est jamais absorbée ;
  * la fusion est journalisée dans le chatter générique (records.Activity).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.crm.services import merge_clients
from apps.installations.models_installation import Installation
from apps.sav.models import Ticket
from apps.ventes.models import Devis, Facture
from authentication.models import Company

User = get_user_model()


class MergeClientsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA18 SA',
                                             slug='ntdata18-sa')
        cls.autre = Company.objects.create(nom='NTDATA18 Autre',
                                           slug='ntdata18-autre')
        cls.user = User.objects.create_user(
            username='ntdata18_u', password='x', company=cls.company,
            role_legacy='admin')

    def setUp(self):
        self.survivant = Client.objects.create(
            company=self.company, nom='Kasri', telephone='0612345678')
        self.doublon = Client.objects.create(
            company=self.company, nom='Kasri R.', telephone='0612345678',
            email='r.kasri@exemple.ma', ice='001234567000089')

    def test_devis_du_doublon_pointent_le_survivant(self):
        devis = Devis.objects.create(
            company=self.company, reference='D-NTDATA18-1',
            client=self.doublon)
        rapport = merge_clients(self.survivant, [self.doublon], self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.client_id, self.survivant.pk)
        self.assertEqual(rapport['absorbes'], [self.doublon.pk])
        self.assertIn('ventes.Devis.client', rapport['repointes'])

    def test_factures_chantiers_tickets_suivent(self):
        facture = Facture.objects.create(
            company=self.company, reference='F-NTDATA18-1',
            client=self.doublon, montant_ht=Decimal('100.00'),
            montant_tva=Decimal('20.00'), montant_ttc=Decimal('120.00'))
        chantier = Installation.objects.create(
            company=self.company, reference='CH-NTDATA18-1',
            client=self.doublon)
        ticket = Ticket.objects.create(
            company=self.company, reference='T-NTDATA18-1',
            client=self.doublon)
        lead = Lead.objects.create(company=self.company, nom='Piste',
                                   client=self.doublon)
        merge_clients(self.survivant, [self.doublon], self.user)
        for objet in (facture, chantier, ticket, lead):
            objet.refresh_from_db()
            self.assertEqual(objet.client_id, self.survivant.pk,
                             objet.__class__.__name__)

    def test_doublon_neutralise_jamais_supprime(self):
        merge_clients(self.survivant, [self.doublon], self.user)
        self.doublon.refresh_from_db()
        self.assertTrue(
            Client.objects.filter(pk=self.doublon.pk).exists())
        self.assertTrue(self.doublon.avertissement_bloquant)
        self.assertIn(str(self.survivant.pk),
                      self.doublon.avertissement_vente)
        self.assertEqual(self.doublon.custom_data['fusionne_dans'],
                         self.survivant.pk)
        self.assertEqual(self.doublon.custom_data['fusionne_par'],
                         'ntdata18_u')

    def test_champs_vides_completes_jamais_ecrases(self):
        merge_clients(self.survivant, [self.doublon], self.user)
        self.survivant.refresh_from_db()
        # Vides chez le survivant → repris du doublon.
        self.assertEqual(self.survivant.email, 'r.kasri@exemple.ma')
        self.assertEqual(self.survivant.ice, '001234567000089')
        # Déjà renseigné chez le survivant → JAMAIS écrasé.
        self.assertEqual(self.survivant.nom, 'Kasri')
        self.assertEqual(self.survivant.telephone, '0612345678')

    def test_jamais_cross_tenant(self):
        etranger = Client.objects.create(company=self.autre, nom='Ailleurs')
        rapport = merge_clients(self.survivant, [etranger], self.user)
        self.assertEqual(rapport['absorbes'], [])
        etranger.refresh_from_db()
        self.assertFalse(etranger.avertissement_bloquant)

    def test_survivant_seul_ne_fait_rien(self):
        rapport = merge_clients(self.survivant, [self.survivant], self.user)
        self.assertEqual(rapport['absorbes'], [])

    def test_chatter_trace_la_fusion(self):
        from apps.records.services import chatter_qs

        merge_clients(self.survivant, [self.doublon], self.user)
        corps = [a.body for a in chatter_qs(self.survivant, self.company)]
        self.assertTrue(any('Fusion' in c for c in corps), corps)
        corps_doublon = [a.body for a in chatter_qs(self.doublon,
                                                    self.company)]
        self.assertTrue(any(str(self.survivant.pk) in c
                            for c in corps_doublon), corps_doublon)


class FusionParDataqualityTests(TestCase):
    """La fusion est DÉCLENCHÉE par dataquality, mais EXÉCUTÉE par crm."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA18 DQ',
                                             slug='ntdata18-dq')
        cls.autre = Company.objects.create(nom='NTDATA18 DQ2',
                                           slug='ntdata18-dq2')
        cls.user = User.objects.create_user(
            username='ntdata18_dq', password='x', company=cls.company,
            role_legacy='admin')

    def test_fusion_via_dataquality(self):
        from apps.dataquality.services import fusionner_clients

        survivant = Client.objects.create(company=self.company, nom='A')
        doublon = Client.objects.create(company=self.company, nom='B',
                                        email='b@exemple.ma')
        Devis.objects.create(company=self.company, reference='D-NTDATA18-2',
                             client=doublon, date_validite=date(2026, 12, 31))
        rapport = fusionner_clients(self.company, self.user, survivant.pk,
                                    [doublon.pk])
        self.assertEqual(rapport['absorbes'], [doublon.pk])

    def test_survivant_d_une_autre_societe_refuse(self):
        from apps.dataquality.services import fusionner_clients

        etranger = Client.objects.create(company=self.autre, nom='Ailleurs')
        doublon = Client.objects.create(company=self.company, nom='B')
        with self.assertRaises(ValueError) as ctx:
            fusionner_clients(self.company, self.user, etranger.pk,
                              [doublon.pk])
        self.assertIn('introuvable', str(ctx.exception))

    def test_sans_doublon_refuse(self):
        from apps.dataquality.services import fusionner_clients

        survivant = Client.objects.create(company=self.company, nom='A')
        with self.assertRaises(ValueError):
            fusionner_clients(self.company, self.user, survivant.pk, [])
