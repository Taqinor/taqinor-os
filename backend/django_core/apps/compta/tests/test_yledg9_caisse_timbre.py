"""Tests YLEDG9 — un encaissement ESPÈCES route par le module caisse (mouvement
posté + timbre fiscal « à verser », exactement une fois) au lieu de
l'écriture banque directe ; un règlement virement n'en crée pas ; sans caisse
configurée, fallback inchangé (``ecriture_pour_paiement``)."""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import (
    CompteTresorerie, EcritureComptable, MouvementCaisse, TimbreFiscal,
)
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from core.events import facture_emise, paiement_enregistre

from apps.compta import receivers  # noqa: F401  (câblage ready())


def make_company(slug='yledg9-co', nom='YLEDG9 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L9',
            email='yledg9@example.com', telephone='+212600000091')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG9',
            prix_vente=Decimal('1000'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG9-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))


class TestPaiementEspecesAvecCaisse(_Base):
    def _make_caisse(self):
        compta_services.seed_plan_comptable(self.company)
        compta_services.seed_journaux(self.company)
        compte_treso = CompteTresorerie.objects.create(
            company=self.company, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse terrain',
            compte_comptable=compta_services.get_compte(self.company, '5161'))
        return compta_services.creer_caisse(
            self.company, compte_treso, libelle='Caisse principale')

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_paiement_especes_cree_mouvement_caisse_et_timbre(self):
        self._make_caisse()
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.ESPECES)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)

        mouvements = MouvementCaisse.objects.filter(company=self.company)
        self.assertEqual(mouvements.count(), 1)
        mouvement = mouvements.first()
        self.assertTrue(mouvement.posted)
        self.assertEqual(mouvement.montant, Decimal('1200'))

        # Exactement une écriture pour ce paiement (jamais deux).
        ecritures_paiement = EcritureComptable.objects.filter(
            company=self.company, source_type='paiement',
            source_id=paiement.id)
        self.assertEqual(ecritures_paiement.count(), 1)

        timbres = TimbreFiscal.objects.filter(
            company=self.company, paiement_id=paiement.id)
        self.assertEqual(timbres.count(), 1)
        self.assertEqual(timbres.first().statut, TimbreFiscal.Statut.A_VERSER)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_paiement_virement_ne_cree_pas_de_mouvement_caisse(self):
        self._make_caisse()
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)

        self.assertEqual(
            MouvementCaisse.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            TimbreFiscal.objects.filter(company=self.company).count(), 0)
        ecritures_paiement = EcritureComptable.objects.filter(
            company=self.company, source_type='paiement',
            source_id=paiement.id)
        self.assertEqual(ecritures_paiement.count(), 1)


class TestPaiementEspecesSansCaisse(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_fallback_ecriture_directe_sans_caisse(self):
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1200'), date_paiement='2026-07-01',
            mode=Paiement.Mode.ESPECES)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)

        self.assertEqual(MouvementCaisse.objects.count(), 0)
        ecritures_paiement = EcritureComptable.objects.filter(
            company=self.company, source_type='paiement',
            source_id=paiement.id)
        self.assertEqual(ecritures_paiement.count(), 1)
