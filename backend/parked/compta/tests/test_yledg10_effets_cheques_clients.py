"""Tests YLEDG10 — Chèques clients reçus → portefeuille d'effets.

Couvre :
  * un paiement mode ``cheque`` crée l'Effet au portefeuille (sens
    ``recevoir``) SANS écriture banque directe (pas de source_type=
    'paiement' tant qu'aucun bordereau n'a été postée) ;
  * un paiement ``virement`` reste en écriture banque directe (comportement
    YLEDG1 inchangé) ;
  * le rejet de l'effet (``rejeter_effet``) route vers
    ``ventes.services.rejeter_paiement`` (YLEDG5) : rouvre la facture, trace
    les frais, idempotent (un 2e rejet du même paiement est un no-op).
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import EcritureComptable, Effet
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from core.events import facture_emise, paiement_enregistre

from apps.compta import receivers  # noqa: F401  (câblage ready())
from apps.ventes import receivers as ventes_receivers  # noqa: F401


def make_company(slug='yledg10-co', nom='YLEDG10 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        compta_services.seed_plan_comptable(self.company)
        compta_services.seed_journaux(self.company)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='L10',
            email='yledg10@example.com', telephone='+212600001001')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-YLEDG10',
            prix_vente=Decimal('1200'), quantite_stock=10,
            tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-YLEDG10-0001',
            client=self.cl, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Onduleur', quantite=Decimal('1'),
            prix_unitaire=Decimal('1200'), taux_tva=Decimal('20.00'))
        facture_emise.send(
            sender=Facture, instance=self.facture, company=self.company)

    def _paiement_cheque(self, montant='1440'):
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal(montant), date_paiement='2026-07-01',
            mode=Paiement.Mode.CHEQUE, reference='CHQ-0001', created_by=None)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        return paiement


class TestPaiementChequeCreeEffet(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_cheque_cree_effet_portefeuille_sans_ecriture_banque_directe(self):
        paiement = self._paiement_cheque()
        effet = Effet.objects.filter(
            company=self.company, sens=Effet.Sens.RECEVOIR,
            tiers_type='client', tiers_id=self.cl.id).first()
        self.assertIsNotNone(effet)
        self.assertEqual(effet.statut, Effet.Statut.PORTEFEUILLE)
        self.assertEqual(effet.montant, Decimal('1440'))
        # Aucune écriture 'paiement' postée directement en banque pour ce
        # règlement (l'argent n'est pas encore là — le portefeuille
        # remplace l'écriture directe).
        self.assertFalse(
            EcritureComptable.objects.filter(
                company=self.company, source_type='paiement',
                source_id=paiement.id).exists())

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_cheque_idempotent_un_seul_effet(self):
        paiement = self._paiement_cheque()
        # Ré-émission (best-effort, ex. re-sauvegarde) : jamais un 2e effet.
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        self.assertEqual(
            Effet.objects.filter(
                company=self.company, commentaire=f'PAIEMENT-{paiement.id}'
            ).count(), 1)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_virement_reste_ecriture_banque_directe(self):
        paiement = Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('1440'), date_paiement='2026-07-01',
            mode=Paiement.Mode.VIREMENT, created_by=None)
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=self.company)
        self.assertTrue(
            EcritureComptable.objects.filter(
                company=self.company, source_type='paiement',
                source_id=paiement.id).exists())
        self.assertEqual(
            Effet.objects.filter(company=self.company).count(), 0)


class TestRejetEffetRouvreFacture(_Base):
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_rejet_effet_rouvre_facture_et_trace_frais(self):
        paiement = self._paiement_cheque()
        effet = Effet.objects.get(commentaire=f'PAIEMENT-{paiement.id}')
        compta_services.rejeter_effet(
            effet, date_rejet='2026-07-05', frais_rejet=Decimal('50'),
            commentaire='Provision insuffisante')
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, Paiement.Statut.REJETE)
        self.assertEqual(paiement.frais_rejet, Decimal('50'))
        self.facture.refresh_from_db()
        self.assertIn(
            self.facture.statut,
            (Facture.Statut.EMISE, Facture.Statut.EN_RETARD))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_rejet_idempotent_un_seul_rejet(self):
        paiement = self._paiement_cheque()
        effet = Effet.objects.get(commentaire=f'PAIEMENT-{paiement.id}')
        compta_services.rejeter_effet(effet, date_rejet='2026-07-05')
        # Un 2e rejet de l'EFFET est lui-même idempotent côté compta
        # (statut déjà 'impaye' → return anticipé) et le récepteur ventes ne
        # tente donc jamais un second rejet du même paiement.
        compta_services.rejeter_effet(effet, date_rejet='2026-07-06')
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, Paiement.Statut.REJETE)
