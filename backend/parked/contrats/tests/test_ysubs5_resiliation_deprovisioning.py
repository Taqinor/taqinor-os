"""Tests YSUBS5 — Résiliation de contrat sans propagation aval
(de-provisioning).

Couvre : résilier un contrat lié à une maintenance stoppe ses visites
futures + sa facturation (via l'événement ``contrat_resilie`` + le récepteur
``apps.sav.receivers``), les échéances futures non facturées passent
``annulee``, un contrat sans lien ne casse rien, idempotence.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, EcheancierContrat, LigneEcheance
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client X'):
    return Client.objects.create(company=company, nom=nom)


def make_contrat_resiliable(company, client=None, **kwargs):
    contrat = Contrat.objects.create(
        company=company, objet=kwargs.pop('objet', 'Contrat résiliable'),
        statut=Contrat.Statut.ACTIF,
        client_id=client.id if client else None, **kwargs)
    return contrat


class ResiliationSansLienTests(TestCase):
    """Un contrat SANS aucun lien maintenance : la résiliation ne casse rien
    (no-op silencieux côté sav)."""

    def setUp(self):
        self.company = make_company('ysubs5-sanslien', 'SansLien')

    def test_resiliation_sans_lien_ne_leve_rien(self):
        contrat = make_contrat_resiliable(self.company)
        resiliation = services.resilier_contrat(contrat, motif='Test')
        self.assertIsNotNone(resiliation.pk)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.RESILIE)


class ResiliationAvecMaintenanceLieeTests(TestCase):
    def setUp(self):
        self.company = make_company('ysubs5-maint', 'Maint')
        self.client_obj = make_client(self.company)
        self.contrat_maintenance = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='mensuel', date_debut=timezone.localdate(),
            prix=Decimal('500'), actif=True, facturation_active=True)
        self.contrat = make_contrat_resiliable(
            self.company, client=self.client_obj,
            sav_contrat_maintenance_id=self.contrat_maintenance.id)

    def test_resiliation_stoppe_visites_et_facturation(self):
        services.resilier_contrat(self.contrat, motif='Fin de maintenance')

        self.contrat_maintenance.refresh_from_db()
        self.assertFalse(self.contrat_maintenance.actif)
        self.assertFalse(self.contrat_maintenance.facturation_active)

    def test_idempotence_deux_appels_sur_maintenance_deja_off(self):
        services.resilier_contrat(self.contrat, motif='Fin')
        self.contrat_maintenance.refresh_from_db()
        self.assertFalse(self.contrat_maintenance.actif)

        # Une seconde résiliation est refusée (garde d'idempotence CONTRAT25)
        # mais ne doit pas re-planter le récepteur / la maintenance reste off.
        with self.assertRaises(services.ResiliationError):
            services.resilier_contrat(self.contrat, motif='Deuxième tentative')
        self.contrat_maintenance.refresh_from_db()
        self.assertFalse(self.contrat_maintenance.actif)
        self.assertFalse(self.contrat_maintenance.facturation_active)


class ResiliationEcheancesFuturesTests(TestCase):
    def setUp(self):
        self.company = make_company('ysubs5-echeance', 'Echeance')
        self.client_obj = make_client(self.company)
        self.contrat = make_contrat_resiliable(
            self.company, client=self.client_obj)
        self.echeancier = EcheancierContrat.objects.create(
            company=self.company, contrat=self.contrat,
            periodicite='mensuelle', facturation_active=True,
            statut=EcheancierContrat.Statut.ACTIF)

    def test_echeances_futures_non_facturees_annulees(self):
        ligne_future = services.ajouter_ligne_echeance(
            self.echeancier,
            date_echeance=timezone.localdate() + timedelta(days=30),
            montant=Decimal('1000'))

        services.resilier_contrat(self.contrat, motif='Fin')

        ligne_future.refresh_from_db()
        self.assertEqual(ligne_future.statut, LigneEcheance.Statut.ANNULEE)

    def test_echeances_deja_facturees_non_touchees(self):
        ligne_passee = services.ajouter_ligne_echeance(
            self.echeancier,
            date_echeance=timezone.localdate() - timedelta(days=5),
            montant=Decimal('1000'))
        ligne_passee.facture_id = 999
        ligne_passee.save(update_fields=['facture_id'])
        statut_avant = ligne_passee.statut

        services.resilier_contrat(self.contrat, motif='Fin')

        ligne_passee.refresh_from_db()
        self.assertEqual(ligne_passee.statut, statut_avant)
        self.assertNotEqual(ligne_passee.statut, LigneEcheance.Statut.ANNULEE)

    def test_echeance_passee_non_facturee_non_touchee(self):
        """Seules les échéances FUTURES sont annulées — une échéance passée
        non facturée (en_retard, p. ex.) reste inchangée (hors périmètre
        YSUBS5, qui vise la facturation récurrente à venir)."""
        ligne_passee = services.ajouter_ligne_echeance(
            self.echeancier,
            date_echeance=timezone.localdate() - timedelta(days=1),
            montant=Decimal('1000'))

        services.resilier_contrat(self.contrat, motif='Fin')

        ligne_passee.refresh_from_db()
        self.assertNotEqual(ligne_passee.statut, LigneEcheance.Statut.ANNULEE)
