"""Tests YLEDG8 — Relier le PaymentRun compta (FG133) aux factures
fournisseurs stock : proposition des échéances dues + statuts soldés.

Couvre :
  * ``proposer`` remplit la campagne depuis les factures fournisseur
    ouvertes (triées par échéance), idempotent (n'ajoute jamais deux fois la
    même facture) ;
  * ``poster`` passe les FF réglées en ``payee``/``partiellement_payee``
    avec leurs ``PaiementFournisseur`` créés une seule fois ;
  * une ligne libre (sans ``facture_fournisseur_id``) reste inchangée.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.compta import services
from apps.compta.models import CompteTresorerie
from apps.stock.models import FactureFournisseur, Fournisseur, PaiementFournisseur


def make_company(slug='yledg8-co', nom='YLEDG8 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)
        self.banque = CompteTresorerie.objects.create(
            company=self.company, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE',
            compte_comptable=services.get_compte(self.company, '5141'))
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YLEDG8', rib='011780000012345678901234')
        self.today = timezone.localdate()
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-YLEDG8-0001',
            fournisseur=self.fournisseur,
            date_echeance=self.today - timedelta(days=5),
            montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'),
            montant_ttc=Decimal('10000'))


class TestProposer(_Base):
    def test_proposer_remplit_depuis_factures_ouvertes(self):
        run = services.creer_payment_run(
            self.company, date_paiement=self.today,
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RUN-YLEDG8-1')
        lignes = services.proposer_lignes_payment_run(run)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].facture_fournisseur_id, self.facture.id)
        self.assertEqual(lignes[0].montant, Decimal('10000'))
        run.refresh_from_db()
        self.assertEqual(run.total, Decimal('10000'))

    def test_proposer_idempotent(self):
        run = services.creer_payment_run(
            self.company, date_paiement=self.today,
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RUN-YLEDG8-2')
        services.proposer_lignes_payment_run(run)
        ajoutees_2 = services.proposer_lignes_payment_run(run)
        self.assertEqual(ajoutees_2, [])
        self.assertEqual(run.lignes.count(), 1)

    def test_facture_payee_absente_de_la_proposition(self):
        PaiementFournisseur.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('10000'), date_paiement=self.today,
            mode='virement')
        run = services.creer_payment_run(
            self.company, date_paiement=self.today,
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RUN-YLEDG8-3')
        lignes = services.proposer_lignes_payment_run(run)
        self.assertEqual(lignes, [])


class TestPosterCreeReglement(_Base):
    def test_poster_cree_paiement_fournisseur_et_solde_la_facture(self):
        run = services.creer_payment_run(
            self.company, date_paiement=self.today,
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RUN-YLEDG8-4')
        services.proposer_lignes_payment_run(run)
        services.poster_payment_run(run)

        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, FactureFournisseur.Statut.PAYEE)
        self.assertEqual(self.facture.solde_du, Decimal('0'))
        self.assertEqual(
            PaiementFournisseur.objects.filter(facture=self.facture).count(), 1)

    def test_poster_idempotent_un_seul_paiement(self):
        run = services.creer_payment_run(
            self.company, date_paiement=self.today,
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RUN-YLEDG8-5')
        services.proposer_lignes_payment_run(run)
        services.poster_payment_run(run)
        services.poster_payment_run(run)  # 2e appel : idempotent (run.posted).
        self.assertEqual(
            PaiementFournisseur.objects.filter(facture=self.facture).count(), 1)

    def test_ligne_libre_sans_reference_inchangee(self):
        run = services.creer_payment_run(
            self.company, date_paiement=self.today,
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RUN-YLEDG8-6',
            lignes=[{'tiers_id': 999, 'montant': Decimal('500'),
                     'reference': 'LIBRE', 'beneficiaire': 'Tiers libre',
                     'rib': '011780000012345678901234'}])
        services.poster_payment_run(run)
        # Aucune facture fournisseur créée/modifiée pour la ligne libre.
        self.assertEqual(
            PaiementFournisseur.objects.filter(
                facture__reference='LIBRE').count(), 0)

    def test_paiement_partiel_laisse_partiellement_payee(self):
        run = services.creer_payment_run(
            self.company, date_paiement=self.today,
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RUN-YLEDG8-7',
            lignes=[{'tiers_id': self.fournisseur.id, 'montant': Decimal('4000'),
                     'reference': self.facture.reference,
                     'beneficiaire': self.fournisseur.nom,
                     'rib': self.fournisseur.rib}])
        ligne = run.lignes.first()
        ligne.facture_fournisseur_id = self.facture.id
        ligne.save(update_fields=['facture_fournisseur_id'])
        services.poster_payment_run(run)
        self.facture.refresh_from_db()
        self.assertEqual(
            self.facture.statut, FactureFournisseur.Statut.PARTIELLEMENT_PAYEE)
        self.assertEqual(self.facture.solde_du, Decimal('6000'))
