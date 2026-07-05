"""YSUBS9 — Période de service (du/au) sur les factures récurrentes.

Couvre :
  * `creer_facture_contrat` (FG40, sav) pose `periode_service_debut/fin`
    correctement depuis `derniere_facturation`/`date_debut` + la périodicité ;
  * `facturer_ligne_echeance` (CONTRAT31, contrats) pose la période depuis
    l'échéance précédente → cette échéance ;
  * une facture NON récurrente (créée à la main) reste à NULL ;
  * la période s'affiche sur le PDF facture (rendu sans lever).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture
from apps.ventes.services import creer_facture_contrat


def make_company(slug='ysubs9-co', nom='YSUBS9 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestPeriodeServiceContratMaintenance(TestCase):
    """FG40 — creer_facture_contrat (sav.ContratMaintenance)."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSUBS9',
            telephone='+212600000091')

    def _contrat(self, **extra):
        from apps.sav.models import ContratMaintenance
        defaults = dict(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=True, prix=Decimal('3000'), facturation_active=True,
        )
        defaults.update(extra)
        return ContratMaintenance.objects.create(**defaults)

    def test_premiere_facture_periode_depuis_date_debut(self):
        contrat = self._contrat(derniere_facturation=None)
        facture = creer_facture_contrat(
            contrat=contrat, user=None, company=self.company)
        self.assertEqual(facture.periode_service_debut, date(2024, 1, 1))
        self.assertEqual(facture.periode_service_fin, date(2025, 1, 1))

    def test_facture_suivante_periode_depuis_derniere_facturation(self):
        contrat = self._contrat(derniere_facturation=date(2025, 1, 1))
        facture = creer_facture_contrat(
            contrat=contrat, user=None, company=self.company)
        self.assertEqual(facture.periode_service_debut, date(2025, 1, 1))
        self.assertEqual(facture.periode_service_fin, date(2026, 1, 1))

    def test_periodicite_mensuelle(self):
        contrat = self._contrat(
            periodicite='mensuel', derniere_facturation=date(2026, 6, 1))
        facture = creer_facture_contrat(
            contrat=contrat, user=None, company=self.company)
        self.assertEqual(facture.periode_service_debut, date(2026, 6, 1))
        self.assertEqual(facture.periode_service_fin, date(2026, 7, 1))


class TestPeriodeServiceEcheancierContrat(TestCase):
    """CONTRAT31 — facturer_ligne_echeance (contrats.EcheancierContrat)."""

    def setUp(self):
        self.company = make_company('ysubs9-ctr-co', 'YSUBS9 CTR Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSUBS9CTR',
            telephone='+212600000092')

    def _echeancier_avec_lignes(self):
        from apps.contrats.models import (
            Contrat, EcheancierContrat, LigneEcheance,
        )
        contrat = Contrat.objects.create(
            company=self.company, client_id=self.client_obj.id,
            date_debut=date(2026, 1, 1), type_contrat='maintenance',
            objet='Contrat de maintenance YSUBS9',
        )
        echeancier = EcheancierContrat.objects.create(
            company=self.company, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True,
        )
        ligne1 = LigneEcheance.objects.create(
            company=self.company, echeancier=echeancier, numero=1,
            date_echeance=date(2026, 2, 1), montant=Decimal('500'))
        ligne2 = LigneEcheance.objects.create(
            company=self.company, echeancier=echeancier, numero=2,
            date_echeance=date(2026, 3, 1), montant=Decimal('500'))
        return contrat, echeancier, ligne1, ligne2

    def test_premiere_echeance_periode_depuis_date_debut_contrat(self):
        from apps.contrats.services import facturer_ligne_echeance
        contrat, echeancier, ligne1, ligne2 = self._echeancier_avec_lignes()
        facture = facturer_ligne_echeance(ligne1, user=None)
        self.assertEqual(facture.periode_service_debut, date(2026, 1, 1))
        self.assertEqual(facture.periode_service_fin, date(2026, 2, 1))

    def test_deuxieme_echeance_periode_depuis_echeance_precedente(self):
        from apps.contrats.services import facturer_ligne_echeance
        contrat, echeancier, ligne1, ligne2 = self._echeancier_avec_lignes()
        facturer_ligne_echeance(ligne1, user=None)
        facture2 = facturer_ligne_echeance(ligne2, user=None)
        self.assertEqual(facture2.periode_service_debut, date(2026, 2, 1))
        self.assertEqual(facture2.periode_service_fin, date(2026, 3, 1))


class TestFactureNonRecurrenteInchangee(TestCase):
    def test_facture_manuelle_periode_null(self):
        company = make_company('ysubs9-manuel-co', 'YSUBS9 Manuel Co')
        client_obj = Client.objects.create(
            company=company, nom='Client', prenom='Manuel',
            telephone='+212600000093')
        facture = Facture.objects.create(
            company=company, reference='FAC-YSUBS9-MANUEL',
            client=client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        self.assertIsNone(facture.periode_service_debut)
        self.assertIsNone(facture.periode_service_fin)


class TestPdfAffichePeriode(TestCase):
    def test_pdf_facture_rend_sans_lever_avec_periode(self):
        from apps.ventes.utils.pdf import generate_facture_pdf
        company = make_company('ysubs9-pdf-co', 'YSUBS9 Pdf Co')
        client_obj = Client.objects.create(
            company=company, nom='Client', prenom='Pdf',
            telephone='+212600000094')
        facture = Facture.objects.create(
            company=company, reference='FAC-YSUBS9-PDF',
            client=client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ttc=Decimal('1200'),
            periode_service_debut=date(2026, 1, 1),
            periode_service_fin=date(2026, 2, 1))
        # Rendu réel (WeasyPrint) — ne doit jamais lever avec la période posée.
        generate_facture_pdf(facture.id)
        facture.refresh_from_db()
        self.assertTrue(facture.fichier_pdf)
