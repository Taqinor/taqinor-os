"""XACC1 — TVA sur encaissement : transfert du compte d'attente.

Couvre :

* régime « débit » (défaut) : ``transferer_tva_encaissement`` ne poste rien
  (non-régression, comportement historique inchangé) ;
* régime « encaissement » : un paiement PARTIEL transfère la TVA au prorata
  du montant réglé, écriture équilibrée (44551 → 4455) ;
* idempotence : rejouer le même paiement ne recrée pas l'écriture ;
* le verrou de période est respecté (période clôturée → refus) ;
* ``regime_tva_societe`` sème le plan comptable au besoin et renvoie le
  réglage société.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CompteComptable, EcritureComptable, LigneEcriture, PlanComptable,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class _FakeDoc(SimpleNamespace):
    """Stub duck-typé d'un document ventes (lu par valeur, jamais importé)."""


class RegimeTvaSocieteTests(TestCase):
    def test_defaut_debit_sans_seed_prealable(self):
        co = make_company('tva-enc-defaut', 'TVA Encaissement Défaut')
        # Société jamais semée : le réglage reste lisible (sème au besoin).
        self.assertEqual(
            services.regime_tva_societe(co), PlanComptable.RegimeTVA.DEBIT)
        self.assertTrue(PlanComptable.objects.filter(company=co).exists())

    def test_bascule_encaissement(self):
        co = make_company('tva-enc-bascule', 'TVA Encaissement Bascule')
        plan = services.seed_plan_comptable(co)
        plan.regime_tva = PlanComptable.RegimeTVA.ENCAISSEMENT
        plan.save(update_fields=['regime_tva'])
        self.assertEqual(
            services.regime_tva_societe(co),
            PlanComptable.RegimeTVA.ENCAISSEMENT)


class TransfertTvaEncaissementTests(TestCase):
    def setUp(self):
        self.co = make_company('tva-enc', 'TVA Encaissement')
        self.plan = services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def _passer_regime_encaissement(self):
        self.plan.regime_tva = PlanComptable.RegimeTVA.ENCAISSEMENT
        self.plan.save(update_fields=['regime_tva'])

    def _facture(self, id=1, total_ht=Decimal('1000'),
                 total_tva=Decimal('200'), total_ttc=Decimal('1200')):
        return _FakeDoc(
            id=id, company=self.co, reference=f'FAC-{id}',
            client_id=42, total_ht=total_ht, total_tva=total_tva,
            total_ttc=total_ttc)

    def test_regime_debit_ne_poste_rien(self):
        # Défaut = débit : AUCUNE écriture de transfert, quel que soit le
        # paiement (non-régression du comportement historique).
        facture = self._facture()
        paiement = _FakeDoc(
            id=1, company=self.co, montant=Decimal('1200'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        res = services.transferer_tva_encaissement(paiement)
        self.assertIsNone(res)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='tva_encaissement').count(), 0)

    def test_paiement_partiel_transfert_au_prorata(self):
        self._passer_regime_encaissement()
        facture = self._facture()
        # Acompte de 600 sur 1200 TTC (50 %) → 50 % de la TVA (200) = 100.
        paiement = _FakeDoc(
            id=10, company=self.co, montant=Decimal('600'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        ecr = services.transferer_tva_encaissement(paiement)
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_debit, Decimal('100.00'))
        attente = ecr.lignes.get(compte__numero='44551')
        definitif = ecr.lignes.get(compte__numero='4455')
        self.assertEqual(attente.debit, Decimal('100.00'))
        self.assertEqual(definitif.credit, Decimal('100.00'))

    def test_paiement_solde_transfert_reste_de_tva(self):
        self._passer_regime_encaissement()
        facture = self._facture()
        # Deux paiements : 600 puis 600 (solde) → 100 + 100 = 200 (TVA totale).
        p1 = _FakeDoc(
            id=11, company=self.co, montant=Decimal('600'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        p2 = _FakeDoc(
            id=12, company=self.co, montant=Decimal('600'),
            date_paiement=date(2026, 2, 20), mode='virement', facture=facture)
        services.transferer_tva_encaissement(p1)
        services.transferer_tva_encaissement(p2)
        total_transfere = sum(
            (lig.debit for lig in LigneEcriture.objects.filter(
                company=self.co, compte__numero='44551')),
            Decimal('0'))
        self.assertEqual(total_transfere, Decimal('200.00'))

    def test_idempotent_meme_paiement(self):
        self._passer_regime_encaissement()
        facture = self._facture(id=2)
        paiement = _FakeDoc(
            id=20, company=self.co, montant=Decimal('1200'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        a = services.transferer_tva_encaissement(paiement)
        b = services.transferer_tva_encaissement(paiement)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='tva_encaissement').count(), 1)

    def test_facture_sans_tva_ne_poste_rien(self):
        self._passer_regime_encaissement()
        facture = self._facture(
            id=3, total_ht=Decimal('500'), total_tva=Decimal('0'),
            total_ttc=Decimal('500'))
        paiement = _FakeDoc(
            id=30, company=self.co, montant=Decimal('500'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        res = services.transferer_tva_encaissement(paiement)
        self.assertIsNone(res)

    def test_periode_verrouillee_refuse_le_transfert(self):
        self._passer_regime_encaissement()
        facture = self._facture(id=4)
        periode = services.creer_periode(
            self.co, date(2026, 2, 1), date(2026, 2, 28),
            libelle='Février 2026')
        services.cloturer_periode(periode)
        paiement = _FakeDoc(
            id=40, company=self.co, montant=Decimal('1200'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        with self.assertRaises(ValidationError):
            services.transferer_tva_encaissement(paiement)

    def test_montant_supersede_paiement_montant(self):
        self._passer_regime_encaissement()
        facture = self._facture(id=5)
        paiement = _FakeDoc(
            id=50, company=self.co, montant=Decimal('1200'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        ecr = services.transferer_tva_encaissement(paiement, montant=Decimal('300'))
        # 300/1200 = 25 % de 200 = 50.
        self.assertEqual(ecr.total_debit, Decimal('50.00'))

    def test_44551_compte_attente_seme(self):
        self._passer_regime_encaissement()
        facture = self._facture(id=6)
        paiement = _FakeDoc(
            id=60, company=self.co, montant=Decimal('1200'),
            date_paiement=date(2026, 2, 10), mode='virement', facture=facture)
        services.transferer_tva_encaissement(paiement)
        self.assertTrue(
            CompteComptable.objects.filter(
                company=self.co, numero='44551').exists())
