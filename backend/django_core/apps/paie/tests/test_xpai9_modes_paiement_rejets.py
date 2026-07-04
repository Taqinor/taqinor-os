"""Tests XPAI9 — Modes de paiement & suivi des rejets de virement.

Couvre : un ordre de virement exclut les profils espèces/chèque (listés à
part par ``profils_hors_virement`` avec décompte de coupures pour les
espèces), ``marquer_bulletin_paye`` horodate le décompte (idempotent),
rejeter une ligne + réémettre avec un RIB corrigé (jamais de suppression,
garde ordre déjà émis), et l'isolation tenant.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import LigneVirement, PeriodePaie, ProfilPaie
from apps.paie.services import (
    decompte_coupures,
    emettre_ordre_virement,
    ensure_defaults,
    generer_bulletin,
    generer_ordre_virement,
    marquer_bulletin_paye,
    profils_hors_virement,
    reemettre_ligne_virement,
    rejeter_ligne_virement,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ModesPaiementTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai9-modes')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _employe(self, mat, mode=ProfilPaie.MODE_PAIEMENT_VIREMENT,
                 rib='RIB' + '0' * 20, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, rib=rib, mode_paiement=mode,
            affilie_cnss=True, affilie_amo=True)

    def _bulletin_valide(self, profil):
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_ordre_exclut_especes_et_cheque(self):
        p_vir = self._employe('A1', mode=ProfilPaie.MODE_PAIEMENT_VIREMENT)
        p_esp = self._employe('A2', mode=ProfilPaie.MODE_PAIEMENT_ESPECES)
        p_cheq = self._employe('A3', mode=ProfilPaie.MODE_PAIEMENT_CHEQUE)
        self._bulletin_valide(p_vir)
        self._bulletin_valide(p_esp)
        self._bulletin_valide(p_cheq)
        ordre = generer_ordre_virement(self.periode)
        self.assertEqual(ordre.nombre_lignes, 1)

    def test_profils_hors_virement_liste_a_part(self):
        p_esp = self._employe(
            'B1', mode=ProfilPaie.MODE_PAIEMENT_ESPECES, salaire=Decimal('4000'))
        self._bulletin_valide(p_esp)
        hors = profils_hors_virement(self.periode)
        self.assertEqual(len(hors), 1)
        self.assertEqual(hors[0]['mode_paiement'], 'especes')
        self.assertIn('decompte_especes', hors[0])

    def test_decompte_coupures_somme_correcte(self):
        decompte = decompte_coupures(Decimal('1237'))
        total = sum(coupure * qte for coupure, qte in decompte.items())
        self.assertEqual(total, 1237)

    def test_marquer_bulletin_paye_idempotent(self):
        p1 = self._employe('C1')
        b = self._bulletin_valide(p1)
        self.assertFalse(b.paye)
        marquer_bulletin_paye(b)
        b.refresh_from_db()
        self.assertTrue(b.paye)
        self.assertIsNotNone(b.date_paiement)
        premiere_date = b.date_paiement
        marquer_bulletin_paye(b)
        b.refresh_from_db()
        self.assertEqual(b.date_paiement, premiere_date)


class RejetVirementTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai9-rejet')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='D1', nom='NomD1', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib='RIBINVALIDE',
            affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(self.profil, self.periode)
        valider_bulletin(b)
        self.ordre = generer_ordre_virement(self.periode)
        self.ligne = self.ordre.lignes.first()

    def test_rejeter_ne_supprime_pas(self):
        rejeter_ligne_virement(self.ligne, motif='RIB inexistant')
        self.ligne.refresh_from_db()
        self.assertTrue(self.ligne.rejetee)
        self.assertEqual(self.ligne.motif_rejet, 'RIB inexistant')
        self.assertIsNotNone(self.ligne.date_rejet)
        self.assertTrue(
            LigneVirement.objects.filter(pk=self.ligne.pk).exists())

    def test_rejeter_idempotent(self):
        rejeter_ligne_virement(self.ligne, motif='premier motif')
        self.ligne.refresh_from_db()
        premiere_date = self.ligne.date_rejet
        rejeter_ligne_virement(self.ligne, motif='second motif')
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.motif_rejet, 'premier motif')
        self.assertEqual(self.ligne.date_rejet, premiere_date)

    def test_reemettre_cree_nouvelle_ligne_corrigee(self):
        rejeter_ligne_virement(self.ligne, motif='RIB invalide')
        nouvelle = reemettre_ligne_virement(
            self.ligne, nouveau_rib='RIBCORRIGE0000000000')
        self.assertNotEqual(nouvelle.id, self.ligne.id)
        self.assertEqual(nouvelle.rib, 'RIBCORRIGE0000000000')
        self.assertEqual(nouvelle.montant, self.ligne.montant)
        self.assertEqual(nouvelle.bulletin_id, self.ligne.bulletin_id)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.ligne_correction_id, nouvelle.id)
        # La ligne originale n'est jamais modifiée (RIB d'origine conservé).
        self.assertEqual(self.ligne.rib, 'RIBINVALIDE')

    def test_reemettre_refuse_ligne_non_rejetee(self):
        with self.assertRaises(ValueError):
            reemettre_ligne_virement(self.ligne, nouveau_rib='X')

    def test_reemettre_refuse_ordre_emis(self):
        rejeter_ligne_virement(self.ligne, motif='RIB invalide')
        emettre_ordre_virement(self.ordre)
        with self.assertRaises(ValueError):
            reemettre_ligne_virement(self.ligne, nouveau_rib='NOUVEAU')

    def test_isolation_tenant(self):
        autre = make_company('xpai9-rejet-autre')
        self.assertFalse(
            LigneVirement.objects.filter(company=autre).exists())
