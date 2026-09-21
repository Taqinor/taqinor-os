"""Tests YLEDG2 — compta s'abonne à ``facture_fournisseur_creee``/
``paiement_fournisseur_enregistre`` (core.events, M6) et génère l'écriture
d'achat correspondante, exactement une fois, quand ``COMPTA_AUTO_ECRITURES``
est actif ; toggle OFF (défaut) → aucune écriture (comportement inchangé).
``apps.compta`` n'importe jamais ``apps.stock`` : les instances transitent
par les arguments du signal (lues uniquement par attribut public), comme
``ecriture_pour_facture_fournisseur``/``ecriture_pour_paiement_fournisseur``
existants (COMPTA15/16)."""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta.models import EcritureComptable
from apps.stock.models import FactureFournisseur, Fournisseur, PaiementFournisseur
from core.events import facture_fournisseur_creee, paiement_fournisseur_enregistre

from apps.compta import receivers  # noqa: F401  (câblage ready())


def make_company(slug='yledg2-co', nom='YLEDG2 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YLEDG2')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-YLEDG2-0001',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), date_facture='2026-07-01')


class TestFactureFournisseurCreeeGenerateEcriture(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_signal_creates_ecriture_once(self):
        facture_fournisseur_creee.send(
            sender=FactureFournisseur, instance=self.facture,
            company=self.company)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='facture_fournisseur',
            source_id=self.facture.id)
        self.assertEqual(qs.count(), 1)
        facture_fournisseur_creee.send(
            sender=FactureFournisseur, instance=self.facture,
            company=self.company)
        self.assertEqual(qs.count(), 1)

    def test_signal_noop_when_toggle_off(self):
        facture_fournisseur_creee.send(
            sender=FactureFournisseur, instance=self.facture,
            company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)


class TestPaiementFournisseurEnregistreGenerateEcriture(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_signal_creates_ecriture_once(self):
        paiement = PaiementFournisseur.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-02',
            mode='virement')
        paiement_fournisseur_enregistre.send(
            sender=PaiementFournisseur, instance=paiement,
            company=self.company)
        qs = EcritureComptable.objects.filter(
            company=self.company, source_type='paiement_fournisseur',
            source_id=paiement.id)
        self.assertEqual(qs.count(), 1)
        paiement_fournisseur_enregistre.send(
            sender=PaiementFournisseur, instance=paiement,
            company=self.company)
        self.assertEqual(qs.count(), 1)

    def test_signal_noop_when_toggle_off(self):
        paiement = PaiementFournisseur.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-02',
            mode='virement')
        paiement_fournisseur_enregistre.send(
            sender=PaiementFournisseur, instance=paiement,
            company=self.company)
        self.assertEqual(EcritureComptable.objects.count(), 0)
