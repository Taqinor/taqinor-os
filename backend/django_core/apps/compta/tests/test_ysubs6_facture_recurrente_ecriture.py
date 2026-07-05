"""Tests YSUBS6 — les factures récurrentes (``creer_facture_contrat`` FG40 côté
sav, ``facturer_ligne_echeance`` CONTRAT31 côté contrats) émettent désormais
``core.events.facture_emise`` — le seul signal manquant sur ces deux chemins
(YLEDG1 a déjà câblé le reste : ``compta.receivers`` s'y abonne, gardé par le
toggle ``COMPTA_AUTO_ECRITURES``). Avec le toggle ON, l'écriture GL équilibrée
est postée exactement une fois ; OFF (défaut) → aucune écriture, comportement
inchangé. ``apps.compta`` n'importe jamais ``ventes``/``contrats``/``sav`` —
seule l'écriture GL est vérifiée ici, jamais leurs modèles internes créés au
delà des fixtures nécessaires."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.compta.models import EcritureComptable
from apps.crm.models import Client
from apps.ventes.services import creer_facture_contrat

from apps.compta import receivers  # noqa: F401  (câblage ready())


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestFactureEmiseSurContratMaintenance(TestCase):
    """FG40 — creer_facture_contrat (sav.ContratMaintenance)."""

    def setUp(self):
        self.company = make_company('ysubs6-sav-co', 'YSUBS6 SAV Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSUBS6',
            telephone='+212600000961')

    def _contrat(self, **extra):
        from apps.sav.models import ContratMaintenance
        defaults = dict(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=True, prix=Decimal('3000'), facturation_active=True,
        )
        defaults.update(extra)
        return ContratMaintenance.objects.create(**defaults)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_toggle_on_poste_une_ecriture_une_seule_fois(self):
        contrat = self._contrat(derniere_facturation=None)
        facture = creer_facture_contrat(
            contrat=contrat, user=None, company=self.company)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='facture',
            source_id=facture.id)
        self.assertEqual(qs.count(), 1)

    def test_toggle_off_defaut_aucune_ecriture(self):
        contrat = self._contrat(derniere_facturation=None)
        creer_facture_contrat(contrat=contrat, user=None, company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)


class TestFactureEmiseSurEcheancierContrat(TestCase):
    """CONTRAT31 — facturer_ligne_echeance (contrats.EcheancierContrat)."""

    def setUp(self):
        self.company = make_company('ysubs6-ctr-co', 'YSUBS6 Ctr Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client SARL YSUBS6')

    def _ligne(self, montant='1200'):
        from apps.contrats import services as contrats_services
        from apps.contrats.models import Contrat, EcheancierContrat

        contrat = Contrat.objects.create(
            company=self.company, objet='Contrat O&M', montant=Decimal('120000'),
            type_contrat='om', statut='actif',
            client_id=self.client_obj.id,
            date_debut=timezone.localdate() - timedelta(days=10))
        ech = EcheancierContrat.objects.create(
            company=self.company, contrat=contrat, periodicite='mensuelle',
            facturation_active=True)
        ligne = contrats_services.ajouter_ligne_echeance(
            ech, date_echeance=timezone.localdate(), montant=Decimal(montant))
        return contrats_services, ligne

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_toggle_on_poste_une_ecriture_une_seule_fois(self):
        contrats_services, ligne = self._ligne()
        facture = contrats_services.facturer_ligne_echeance(ligne, user=None)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='facture',
            source_id=facture.id)
        self.assertEqual(qs.count(), 1)

    def test_toggle_off_defaut_aucune_ecriture(self):
        contrats_services, ligne = self._ligne()
        contrats_services.facturer_ligne_echeance(ligne, user=None)
        self.assertEqual(EcritureComptable.objects.count(), 0)
