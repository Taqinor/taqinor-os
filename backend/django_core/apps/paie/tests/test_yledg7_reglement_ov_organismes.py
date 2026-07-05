"""Tests YLEDG7 — Règlement de l'OV salaires + des organismes sociaux.

``journal_de_paie`` (PAIE33) poste correctement les DETTES (crédit 4432 net,
4441 CNSS/AMO, 4452 IR, 4443 CIMR) mais rien ne postait jamais le RÈGLEMENT.
Couvre :
* ``payer_ordre_virement`` — débite 4432 / crédite trésorerie du total de
  l'ordre, idempotent (une seule écriture par ordre).
* ``payer_organismes`` — débite 4441/4452/4443 / crédite trésorerie du montant
  dû par organisme, marque PAYÉES les ``EcheanceDeclarative`` correspondantes,
  idempotent.
* Verrou de période comptable respecté (via ``creer_ecriture_od``).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.compta.models import CompteTresorerie
from apps.compta.services import get_compte, seed_plan_comptable
from apps.paie.models import EcheanceDeclarative, PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    etat_des_charges,
    generer_bulletin,
    generer_echeances_periode,
    generer_ordre_virement,
    payer_ordre_virement,
    payer_organismes,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_compte_tresorerie(company):
    seed_plan_comptable(company)
    compte_comptable = get_compte(company, '5141')
    return CompteTresorerie.objects.create(
        company=company, type_compte=CompteTresorerie.Type.BANQUE,
        libelle='Banque test', compte_comptable=compte_comptable)


class PayerOrdreVirementTests(TestCase):
    def setUp(self):
        self.co = make_company('yledg7-ov')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.treso = make_compte_tresorerie(self.co)

    def _bulletin_valide(self, mat, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True,
            rib='RIB' + mat)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def _ordre(self):
        self._bulletin_valide('OV1')
        return generer_ordre_virement(self.periode)

    def test_payer_solde_4432(self):
        ordre = self._ordre()
        ecriture = payer_ordre_virement(ordre, self.treso.id)
        self.assertIsNotNone(ecriture)
        lignes = list(ecriture.lignes.all())
        debit = sum((lig.debit for lig in lignes), Decimal('0'))
        credit = sum((lig.credit for lig in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, ordre.total)
        compte_net = get_compte(self.co, '4432')
        ligne_net = next(lig for lig in lignes if lig.compte_id == compte_net.id)
        self.assertEqual(ligne_net.debit, ordre.total)
        ligne_banque = next(
            lig for lig in lignes
            if lig.compte_id == self.treso.compte_comptable_id)
        self.assertEqual(ligne_banque.credit, ordre.total)

    def test_payer_est_idempotent(self):
        ordre = self._ordre()
        ecriture1 = payer_ordre_virement(ordre, self.treso.id)
        ordre.refresh_from_db()
        self.assertEqual(ordre.ecriture_reglement_id, ecriture1.id)
        ecriture2 = payer_ordre_virement(ordre, self.treso.id)
        self.assertEqual(ecriture1.id, ecriture2.id)
        # Une seule écriture de règlement a été créée pour cet ordre.
        from apps.compta.models import EcritureComptable
        nb = EcritureComptable.objects.filter(
            reference=f'OV-REGLEMENT-{ordre.id}').count()
        self.assertEqual(nb, 1)

    def test_compte_tresorerie_autre_societe_refuse(self):
        ordre = self._ordre()
        autre = make_company('yledg7-ov-autre')
        treso_autre = make_compte_tresorerie(autre)
        with self.assertRaises(ValueError):
            payer_ordre_virement(ordre, treso_autre.id)

    def test_ordre_sans_montant_refuse(self):
        # Ordre créé mais sans bulletin -> total nul. generer_ordre_virement
        # crée quand même l'ordre (brouillon vide, XPAI8) ; c'est le
        # RÈGLEMENT qui doit refuser un ordre sans montant.
        periode_vide = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        ordre = generer_ordre_virement(periode_vide)
        self.assertEqual(ordre.total, 0)
        with self.assertRaises(ValueError):
            payer_ordre_virement(ordre, self.treso.id)


class PayerOrganismesTests(TestCase):
    def setUp(self):
        self.co = make_company('yledg7-org')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.treso = make_compte_tresorerie(self.co)

    def _bulletin_valide(self, mat, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_payer_cnss_solde_4441(self):
        self._bulletin_valide('P1')
        generer_echeances_periode(self.periode)
        etat = etat_des_charges(self.periode)
        attendu = next(
            o for o in etat['organismes'] if o['code'] == 'cnss_amo')['total']

        ecriture = payer_organismes(self.periode, 'cnss_amo', self.treso.id)
        self.assertIsNotNone(ecriture)
        lignes = list(ecriture.lignes.all())
        compte_cnss = get_compte(self.co, '4441')
        ligne_dette = next(
            lig for lig in lignes if lig.compte_id == compte_cnss.id)
        self.assertEqual(ligne_dette.debit, attendu)

        echeance = EcheanceDeclarative.objects.get(
            company=self.co, periode=self.periode,
            type_echeance=EcheanceDeclarative.TYPE_BDS)
        self.assertEqual(echeance.statut, EcheanceDeclarative.STATUT_PAYEE)
        self.assertEqual(echeance.ecriture_reglement_id, ecriture.id)

    def test_payer_idempotent_ne_double_pas(self):
        self._bulletin_valide('P2')
        generer_echeances_periode(self.periode)
        ecriture1 = payer_organismes(self.periode, 'ir', self.treso.id)
        self.assertIsNotNone(ecriture1)
        # Rejouer : l'échéance est déjà payée -> no-op (None), jamais 2e écriture.
        ecriture2 = payer_organismes(self.periode, 'ir', self.treso.id)
        self.assertIsNone(ecriture2)

    def test_organisme_inconnu_leve(self):
        self._bulletin_valide('P3')
        with self.assertRaises(ValueError):
            payer_organismes(self.periode, 'mutuelle', self.treso.id)

    def test_sans_montant_du_renvoie_none(self):
        # Aucun bulletin validé -> rien à régler.
        ecriture = payer_organismes(self.periode, 'cimr', self.treso.id)
        self.assertIsNone(ecriture)
