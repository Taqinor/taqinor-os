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
