"""Tests YSUBS1 — Beat quotidien : facturation récurrente auto (échéanciers
contrats + maintenance).

Couvre : une ligne d'échéance due est facturée automatiquement par le beat
(date injectée), un contrat de maintenance dû aussi, re-run le même jour ne
re-facture rien (idempotence via ``facture_id``/``derniere_facturation``),
une exception sur un contrat n'empêche pas les suivants, multi-tenant.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, EcheancierContrat
from apps.contrats.scheduled import generer_factures_recurrentes_dues
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client SARL'):
    return Client.objects.create(company=company, nom=nom)


def make_echeance_due(company, client, *, montant='1200'):
    contrat = Contrat.objects.create(
        company=company, objet='Contrat O&M', montant=Decimal('120000'),
        type_contrat='om', statut='actif', client_id=client.id,
        date_debut=timezone.localdate() - timedelta(days=10))
    ech = EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite='mensuelle',
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
    ligne = services.ajouter_ligne_echeance(
        ech, date_echeance=timezone.localdate() - timedelta(days=1),
        montant=Decimal(montant))
    return contrat, ech, ligne


def make_contrat_maintenance_du(company, client, *, prix='500'):
    return ContratMaintenance.objects.create(
        company=company, client=client, periodicite='mensuel',
        date_debut=timezone.localdate() - timedelta(days=35),
        prix=Decimal(prix), actif=True, facturation_active=True)


class BeatFacturationRecurrenteTests(TestCase):
    def setUp(self):
        self.company = make_company('ysubs1', 'YSUBS1')
        self.client_obj = make_client(self.company)

    def test_echeance_due_facturee_automatiquement(self):
        contrat, ech, ligne = make_echeance_due(self.company, self.client_obj)
        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['echeances_facturees'], 1)
        ligne.refresh_from_db()
        self.assertIsNotNone(ligne.facture_id)

    def test_rerun_meme_jour_ne_refacture_rien(self):
        make_echeance_due(self.company, self.client_obj)
        generer_factures_recurrentes_dues()
        resultat2 = generer_factures_recurrentes_dues()
        self.assertEqual(resultat2['echeances_facturees'], 0)

    def test_maintenance_due_facturee_automatiquement(self):
        make_contrat_maintenance_du(self.company, self.client_obj)
        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['maintenances_facturees'], 1)

    def test_maintenance_rerun_meme_jour_idempotent(self):
        contrat_m = make_contrat_maintenance_du(self.company, self.client_obj)
        generer_factures_recurrentes_dues()
        contrat_m.refresh_from_db()
        self.assertIsNotNone(contrat_m.derniere_facturation)
        resultat2 = generer_factures_recurrentes_dues()
        self.assertEqual(resultat2['maintenances_facturees'], 0)

    def test_echeance_non_active_ignoree(self):
        contrat = Contrat.objects.create(
            company=self.company, objet='Contrat X', montant=Decimal('1000'),
            type_contrat='om', statut='actif', client_id=self.client_obj.id)
        ech = EcheancierContrat.objects.create(
            company=self.company, contrat=contrat, periodicite='mensuelle',
            facturation_active=False,
            statut=EcheancierContrat.Statut.ACTIF)
        services.ajouter_ligne_echeance(
            ech, date_echeance=timezone.localdate() - timedelta(days=1),
            montant=Decimal('1000'))
        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['echeances_facturees'], 0)

    def test_echec_un_contrat_n_empeche_pas_les_suivants(self):
        # Contrat SANS client (client_id=None) -> FacturationError attendue,
        # mais ne doit pas bloquer le contrat de maintenance du même run.
        contrat_ko = Contrat.objects.create(
            company=self.company, objet='Sans client',
            montant=Decimal('1000'), type_contrat='om', statut='actif',
            client_id=None)
        ech_ko = EcheancierContrat.objects.create(
            company=self.company, contrat=contrat_ko, periodicite='mensuelle',
            facturation_active=True,
            statut=EcheancierContrat.Statut.ACTIF)
        services.ajouter_ligne_echeance(
            ech_ko, date_echeance=timezone.localdate() - timedelta(days=1),
            montant=Decimal('1000'))

        make_contrat_maintenance_du(self.company, self.client_obj)

        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['echeances_echecs'], 1)
        self.assertEqual(resultat['maintenances_facturees'], 1)

    def test_isolation_societe(self):
        autre_company = make_company('ysubs1-autre', 'Autre')
        autre_client = make_client(autre_company, 'Client autre')
        make_echeance_due(autre_company, autre_client)

        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['echeances_facturees'], 1)
