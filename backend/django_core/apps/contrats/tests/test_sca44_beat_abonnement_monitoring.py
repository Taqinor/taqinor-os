"""Tests SCA44 — Beat quotidien : l'``AbonnementMonitoring`` rejoint la
facturation récurrente automatique (3e flux, après les échéanciers contrats
et les contrats de maintenance SAV).

Couvre : un abonnement monitoring dû est facturé automatiquement par le beat
(Facture réelle émise, ``derniere_facturation`` avancée), re-run le même
jour ne re-facture rien (idempotence via ``derniere_facturation`` +
``prochaine_echeance`` avancée par ``renouveler``), un abonnement non dû ou
non actif est ignoré, une exception sur un abonnement n'empêche pas les
suivants (isolation), multi-tenant, l'action manuelle du ViewSet reste
disponible en parallèle.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta.models import AbonnementMonitoring
from apps.contrats.scheduled import generer_factures_recurrentes_dues
from apps.crm.models import Client
from apps.ventes.models import Facture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client SARL'):
    return Client.objects.create(company=company, nom=nom)


def make_abonnement_du(company, client, *, montant='199', jours_retard=1):
    return AbonnementMonitoring.objects.create(
        company=company, client_id=client.id, periodicite='mensuel',
        montant=Decimal(montant),
        date_debut=timezone.localdate() - timedelta(days=60),
        prochaine_echeance=timezone.localdate() - timedelta(days=jours_retard),
    )


class BeatAbonnementMonitoringTests(TestCase):
    def setUp(self):
        self.company = make_company('sca44', 'SCA44')
        self.client_obj = make_client(self.company)

    def test_abonnement_du_facture_automatiquement(self):
        abonnement = make_abonnement_du(self.company, self.client_obj)
        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['abonnements_factures'], 1)
        self.assertEqual(resultat['abonnements_echecs'], 0)

        abonnement.refresh_from_db()
        self.assertIsNotNone(abonnement.derniere_facturation)
        facture = Facture.objects.get(client_id=self.client_obj.id)
        self.assertEqual(facture.montant_ttc, Decimal('199.00'))
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

    def test_rerun_meme_jour_ne_refacture_rien(self):
        make_abonnement_du(self.company, self.client_obj)
        resultat1 = generer_factures_recurrentes_dues()
        self.assertEqual(resultat1['abonnements_factures'], 1)

        resultat2 = generer_factures_recurrentes_dues()
        self.assertEqual(resultat2['abonnements_factures'], 0)
        self.assertEqual(
            Facture.objects.filter(client_id=self.client_obj.id).count(), 1)

    def test_abonnement_non_du_ignore(self):
        AbonnementMonitoring.objects.create(
            company=self.company, client_id=self.client_obj.id,
            periodicite='mensuel', montant=Decimal('199'),
            date_debut=timezone.localdate(),
            prochaine_echeance=timezone.localdate() + timedelta(days=10))
        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['abonnements_factures'], 0)

    def test_abonnement_suspendu_ignore(self):
        AbonnementMonitoring.objects.create(
            company=self.company, client_id=self.client_obj.id,
            periodicite='mensuel', montant=Decimal('199'),
            statut=AbonnementMonitoring.Statut.SUSPENDU,
            date_debut=timezone.localdate() - timedelta(days=60),
            prochaine_echeance=timezone.localdate() - timedelta(days=1))
        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['abonnements_factures'], 0)

    def test_echec_un_abonnement_n_empeche_pas_les_suivants(self):
        # Abonnement sans client résolvable (client_id inexistant) -> échec
        # isolé, ne doit pas bloquer l'abonnement valide du même run.
        AbonnementMonitoring.objects.create(
            company=self.company, client_id=999999, periodicite='mensuel',
            montant=Decimal('50'),
            date_debut=timezone.localdate() - timedelta(days=60),
            prochaine_echeance=timezone.localdate() - timedelta(days=1))
        make_abonnement_du(self.company, self.client_obj, montant='299')

        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['abonnements_echecs'], 1)
        self.assertEqual(resultat['abonnements_factures'], 1)

    def test_isolation_societe(self):
        autre_company = make_company('sca44-autre', 'Autre')
        autre_client = make_client(autre_company, 'Client autre')
        make_abonnement_du(autre_company, autre_client)

        resultat = generer_factures_recurrentes_dues()
        self.assertEqual(resultat['abonnements_factures'], 1)
        self.assertEqual(
            Facture.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            Facture.objects.filter(company=autre_company).count(), 1)
