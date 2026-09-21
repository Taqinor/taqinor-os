"""Tests XPAI12 — BDS complémentaire/rectificative + format DAMANCOM strict.

Couvre : une correction post-dépôt produit une BDS COMPLÉMENTAIRE ne
contenant QUE le delta (jamais l'ensemble des salariés à nouveau), référencée
au dépôt principal de la même période ; le fichier eBDS strict respecte les
longueurs du gabarit embarqué.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import DepotBDS, PeriodePaie, ProfilPaie
from apps.paie.services import (
    GABARIT_EBDS_ENTETE,
    GABARIT_EBDS_LIGNE,
    deposer_bds_complementaire,
    deposer_bds_principal,
    ensure_defaults,
    fichier_damancom_strict,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def _longueur_gabarit(gabarit):
    return sum(longueur for _champ, longueur, _remplissage in gabarit)


class DeposerBdsPrincipalTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai12-principal')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, mat):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss=f'CNSS{mat}',
            affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return profil

    def test_depot_principal_idempotent(self):
        self._bulletin_valide('A1')
        depot1 = deposer_bds_principal(self.periode)
        depot2 = deposer_bds_principal(self.periode)
        self.assertEqual(depot1.id, depot2.id)
        self.assertEqual(DepotBDS.objects.filter(
            periode=self.periode, type_depot=DepotBDS.TYPE_PRINCIPAL).count(), 1)


class DeposerBdsComplementaireTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai12-comp')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_refuse_sans_depot_principal(self):
        with self.assertRaises(ValueError):
            deposer_bds_complementaire(self.periode, ['CNSS999'])

    def test_complementaire_contient_seulement_le_delta(self):
        deposer_bds_principal(self.periode)
        complement = deposer_bds_complementaire(
            self.periode, ['CNSS_OMIS_1', 'CNSS_CORRIGE_2'])
        self.assertEqual(complement.type_depot, DepotBDS.TYPE_COMPLEMENTAIRE)
        self.assertEqual(len(complement.profils_couverts), 2)

    def test_reference_depot_principal_meme_periode(self):
        principal = deposer_bds_principal(self.periode)
        complement = deposer_bds_complementaire(self.periode, ['X1'])
        self.assertEqual(complement.depot_principal_id, principal.id)

    def test_plusieurs_complementaires_possibles(self):
        deposer_bds_principal(self.periode)
        c1 = deposer_bds_complementaire(self.periode, ['A'])
        c2 = deposer_bds_complementaire(self.periode, ['B'])
        self.assertNotEqual(c1.id, c2.id)
        self.assertEqual(DepotBDS.objects.filter(
            periode=self.periode,
            type_depot=DepotBDS.TYPE_COMPLEMENTAIRE).count(), 2)


class FichierDamancomStrictTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai12-strict')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, mat):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss=f'CNSS{mat}',
            affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return profil

    def test_entete_longueur_gabarit(self):
        self._bulletin_valide('B1')
        fichier = fichier_damancom_strict(self.periode)
        entete = fichier['lignes'][0]
        self.assertEqual(len(entete), _longueur_gabarit(GABARIT_EBDS_ENTETE))
        self.assertEqual(entete[0], 'E')

    def test_ligne_salarie_longueur_gabarit(self):
        self._bulletin_valide('B2')
        fichier = fichier_damancom_strict(self.periode)
        ligne = fichier['lignes'][1]
        self.assertEqual(len(ligne), _longueur_gabarit(GABARIT_EBDS_LIGNE))
        self.assertEqual(ligne[0], 'S')

    def test_complementaire_ne_formate_que_le_delta(self):
        p1 = self._bulletin_valide('B3')
        self._bulletin_valide('B4')
        deposer_bds_principal(self.periode)
        complement = deposer_bds_complementaire(
            self.periode, [p1.numero_cnss])
        fichier = fichier_damancom_strict(self.periode, depot=complement)
        # 1 en-tête + 1 seul salarié (le delta), pas les 2 de la déclaration.
        self.assertEqual(fichier['nombre_salaries'], 1)
        self.assertEqual(len(fichier['lignes']), 2)
