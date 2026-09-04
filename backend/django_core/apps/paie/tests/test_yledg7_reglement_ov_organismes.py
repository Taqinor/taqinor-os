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

    def test_instance_perimee_ne_double_pas_le_reglement(self):
        """AUD712 — la course « check-then-create » est fermée.

        Reproduction déterministe du motif de course : deux lectures de
        l'ordre AVANT tout paiement (comme deux requêtes concurrentes). La
        seconde instance ne « voit » pas le règlement posé par la première ;
        le contrôle d'état se faisant sur cette instance en mémoire, hors
        transaction et sans verrou, une SECONDE écriture complète était
        postée (double débit 4432 / crédit trésorerie).
        """
        from apps.compta.models import EcritureComptable
        from apps.paie.models import OrdreVirement

        ordre = self._ordre()
        vue_a = OrdreVirement.objects.get(pk=ordre.pk)
        vue_b = OrdreVirement.objects.get(pk=ordre.pk)

        ecriture1 = payer_ordre_virement(vue_a, self.treso.id)
        ecriture2 = payer_ordre_virement(vue_b, self.treso.id)

        self.assertEqual(ecriture1.id, ecriture2.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='paie_ov_reglement',
                source_id=ordre.id).count(), 1)
        # L'instance périmée est resynchronisée sur l'état réel.
        self.assertEqual(vue_b.ecriture_reglement_id, ecriture1.id)

    def test_ecriture_reglement_porte_sa_source(self):
        ordre = self._ordre()
        ecriture = payer_ordre_virement(ordre, self.treso.id)
        self.assertEqual(ecriture.source_type, 'paie_ov_reglement')
        self.assertEqual(ecriture.source_id, ordre.id)

    def test_contrainte_db_refuse_une_seconde_ecriture_meme_source(self):
        """Filet DB : la garde applicative n'est plus le seul rempart."""
        from django.db import IntegrityError, transaction

        from apps.compta.services import creer_ecriture_od, get_compte

        ordre = self._ordre()
        payer_ordre_virement(ordre, self.treso.id)
        compte_net = get_compte(self.co, '4432')
        lignes = [
            {'compte': compte_net, 'libelle': 'Doublon',
             'debit': Decimal('1'), 'credit': Decimal('0')},
            {'compte': self.treso.compte_comptable, 'libelle': 'Doublon',
             'debit': Decimal('0'), 'credit': Decimal('1')},
        ]
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                creer_ecriture_od(
                    self.co, ordre.date_reglement.date(), 'Doublon', lignes,
                    source_type='paie_ov_reglement', source_id=ordre.id)

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

    def test_ecriture_organisme_porte_sa_source(self):
        """AUD712 — une source par organisme ET par période."""
        self._bulletin_valide('P4')
        generer_echeances_periode(self.periode)
        ecriture = payer_organismes(self.periode, 'cnss_amo', self.treso.id)
        self.assertIsNotNone(ecriture)
        self.assertEqual(ecriture.source_type, 'paie_org_cnss_amo')
        self.assertEqual(ecriture.source_id, self.periode.id)

        # Un AUTRE organisme de la même période garde sa propre source : la
        # contrainte d'unicité ne bloque jamais un règlement légitime.
        autre = payer_organismes(self.periode, 'ir', self.treso.id)
        self.assertIsNotNone(autre)
        self.assertEqual(autre.source_type, 'paie_org_ir')
        self.assertEqual(autre.source_id, self.periode.id)

    def test_organisme_inconnu_leve(self):
        self._bulletin_valide('P3')
        with self.assertRaises(ValueError):
            payer_organismes(self.periode, 'mutuelle', self.treso.id)

    def test_sans_montant_du_renvoie_none(self):
        # Aucun bulletin validé -> rien à régler.
        ecriture = payer_organismes(self.periode, 'cimr', self.treso.id)
        self.assertIsNone(ecriture)
