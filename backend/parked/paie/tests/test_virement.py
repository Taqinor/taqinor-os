"""Tests PAIE30 — OrdreVirement + fichier de virement banque.

Couvre :
* ``generer_ordre_virement`` — regroupe les bulletins VALIDÉS au net > 0 ;
  ignore les brouillons ; idempotent (recrée les lignes en brouillon) ;
  refuse de régénérer un ordre émis.
* ``emettre_ordre_virement`` — fige (brouillon → emis), date_emission posée.
* ``fichier_virement_paie`` — lignes + total ; lève si RIB manquant ou aucune
  ligne.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import OrdreVirement, PeriodePaie, ProfilPaie
from apps.paie.services import (
    emettre_ordre_virement,
    ensure_defaults,
    fichier_virement_paie,
    generer_bulletin,
    generer_ordre_virement,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class OrdreVirementTests(TestCase):
    def setUp(self):
        self.co = make_company('ov')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _employe(self, mat, rib='RIB' + '0' * 20):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib=rib,
            affilie_cnss=True, affilie_amo=True)

    def _bulletin_valide(self, profil):
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_regroupe_bulletins_valides(self):
        p1 = self._employe('A1')
        p2 = self._employe('A2')
        b1 = self._bulletin_valide(p1)
        b2 = self._bulletin_valide(p2)
        ordre = generer_ordre_virement(self.periode)
        self.assertEqual(ordre.nombre_lignes, 2)
        self.assertEqual(ordre.total, b1.net_a_payer + b2.net_a_payer)
        self.assertEqual(ordre.statut, OrdreVirement.STATUT_BROUILLON)

    def test_ignore_brouillon(self):
        p1 = self._employe('B1')
        self._bulletin_valide(p1)
        p2 = self._employe('B2')
        generer_bulletin(p2, self.periode)  # brouillon → exclu
        ordre = generer_ordre_virement(self.periode)
        self.assertEqual(ordre.nombre_lignes, 1)

    def test_emettre_fige(self):
        p1 = self._employe('C1')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        emettre_ordre_virement(ordre)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreVirement.STATUT_EMIS)
        self.assertIsNotNone(ordre.date_emission)
        # Régénérer un ordre émis est interdit.
        with self.assertRaises(ValueError):
            generer_ordre_virement(self.periode)

    def test_fichier_virement(self):
        p1 = self._employe('D1')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        fichier = fichier_virement_paie(ordre)
        self.assertEqual(fichier['nb_lignes'], 1)
        self.assertEqual(len(fichier['rows'][0]), len(fichier['headers']))
        self.assertEqual(fichier['total'], ordre.total)

    def test_fichier_rib_manquant(self):
        p1 = self._employe('E1', rib='')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        with self.assertRaises(ValueError):
            fichier_virement_paie(ordre)

    # ── DC20 — compte émetteur = référentiel compta.CompteTresorerie ────────

    def _compte_tresorerie(self, *, company=None, rib='RIBEMET' + '0' * 13,
                           devise='MAD'):
        from apps.compta.models import CompteTresorerie
        from apps.compta.services import get_compte, seed_plan_comptable

        co = company or self.co
        seed_plan_comptable(co)
        cpt = get_compte(co, '5141')
        return CompteTresorerie.objects.create(
            company=co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE Salaires', banque='BMCE',
            rib=rib, iban='MA64' + '0' * 20, devise=devise,
            compte_comptable=cpt)

    def test_compte_emetteur_pilote_rib_et_devise(self):
        p1 = self._employe('F1')
        self._bulletin_valide(p1)
        compte = self._compte_tresorerie(rib='R' + '9' * 19, devise='EUR')
        ordre = generer_ordre_virement(
            self.periode, compte_emetteur=compte.id)
        self.assertEqual(ordre.compte_emetteur_id, compte.id)
        # RIB + devise DÉRIVÉS du référentiel, jamais re-tapés.
        self.assertEqual(ordre.rib_emetteur, 'R' + '9' * 19)
        self.assertEqual(ordre.devise, 'EUR')
        fichier = fichier_virement_paie(ordre)
        self.assertEqual(fichier['emetteur']['rib'], 'R' + '9' * 19)
        self.assertEqual(fichier['emetteur']['banque'], 'BMCE')

    def test_compte_emetteur_autre_societe_ignore(self):
        autre = make_company('ov-autre')
        compte_autre = self._compte_tresorerie(
            company=autre, rib='AUTRE' + '0' * 15)
        p1 = self._employe('G1')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(
            self.periode, compte_emetteur=compte_autre.id)
        # Compte d'une autre société → ignoré (pas de fuite cross-tenant).
        self.assertIsNone(ordre.compte_emetteur_id)

    def test_rib_emetteur_repli_sans_compte(self):
        p1 = self._employe('H1')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(
            self.periode, rib_emetteur='REPLI' + '0' * 15)
        self.assertEqual(ordre.rib_emetteur, 'REPLI' + '0' * 15)
        self.assertIsNone(ordre.compte_emetteur_id)

    # ── DC39 — référence unique générée via create_with_reference ──────────

    def test_reference_generee_format(self):
        p1 = self._employe('I1')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        # OV-YYYYMM-NNNN — généré, jamais count()+1.
        self.assertRegex(ordre.reference, r'^OV-\d{6}-\d{4}$')
        self.assertTrue(ordre.reference.endswith('-0001'))

    def test_reference_stable_a_la_regeneration(self):
        p1 = self._employe('J1')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        ref1 = ordre.reference
        # Régénérer (brouillon) ne crée PAS une 2ᵉ référence : même ordre.
        ordre2 = generer_ordre_virement(self.periode)
        self.assertEqual(ordre2.id, ordre.id)
        self.assertEqual(ordre2.reference, ref1)

    def test_references_uniques_par_periode(self):
        p1 = self._employe('K1')
        self._bulletin_valide(p1)
        ordre1 = generer_ordre_virement(self.periode)
        periode2 = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        p2 = self._employe('K2')
        b2 = generer_bulletin(p2, periode2)
        valider_bulletin(b2)
        ordre2 = generer_ordre_virement(periode2)
        self.assertNotEqual(ordre1.reference, ordre2.reference)
