"""Tests XPAI8 — Fichier de virement SIMT (format bancaire marocain).

Couvre : ``fichier_virement_paie_simt`` produit des enregistrements à
LONGUEURS FIXES (en-tête + une ligne par bénéficiaire), les totaux/nombre de
lignes concordent avec l'ordre, le CSV existant (``fichier_virement_paie``)
reste inchangé, et les mêmes gardes (aucune ligne / RIB manquant) s'appliquent.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    GABARIT_SIMT_ENTETE,
    GABARIT_SIMT_LIGNE,
    ensure_defaults,
    fichier_virement_paie,
    fichier_virement_paie_simt,
    generer_bulletin,
    generer_ordre_virement,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def _longueur_gabarit(gabarit):
    return sum(longueur for _champ, longueur, _remplissage in gabarit)


class FichierVirementSimtTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai8-simt')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _employe(self, mat, rib='RIB' + '0' * 20, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, rib=rib,
            affilie_cnss=True, affilie_amo=True)

    def _bulletin_valide(self, profil):
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_entete_longueur_fixe(self):
        p1 = self._employe('A1')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        fichier = fichier_virement_paie_simt(ordre)
        entete = fichier['lignes'][0]
        self.assertEqual(len(entete), _longueur_gabarit(GABARIT_SIMT_ENTETE))
        self.assertEqual(entete[0], 'E')

    def test_ligne_detail_longueur_fixe(self):
        p1 = self._employe('A2')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        fichier = fichier_virement_paie_simt(ordre)
        ligne = fichier['lignes'][1]
        self.assertEqual(len(ligne), _longueur_gabarit(GABARIT_SIMT_LIGNE))
        self.assertEqual(ligne[0], 'D')

    def test_totaux_egaux_a_ordre(self):
        p1 = self._employe('A3')
        p2 = self._employe('A4')
        self._bulletin_valide(p1)
        self._bulletin_valide(p2)
        ordre = generer_ordre_virement(self.periode)
        fichier = fichier_virement_paie_simt(ordre)
        # 1 en-tête + 1 ligne par bénéficiaire.
        self.assertEqual(len(fichier['lignes']), 1 + fichier['nb_lignes'])
        self.assertEqual(fichier['total'], ordre.total)
        self.assertEqual(fichier['nb_lignes'], ordre.nombre_lignes)

    def test_csv_existant_intact(self):
        p1 = self._employe('A5')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        csv_fichier = fichier_virement_paie(ordre)
        self.assertIn('headers', csv_fichier)
        self.assertIn('rows', csv_fichier)

    def test_rib_manquant_leve(self):
        p1 = self._employe('A6', rib='')
        self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        with self.assertRaises(ValueError):
            fichier_virement_paie_simt(ordre)

    def test_aucune_ligne_leve(self):
        ordre = generer_ordre_virement(self.periode)  # aucun bulletin validé
        with self.assertRaises(ValueError):
            fichier_virement_paie_simt(ordre)

    def test_montant_centimes_dans_ligne_detail(self):
        p1 = self._employe('A7', salaire=Decimal('5000'))
        b1 = self._bulletin_valide(p1)
        ordre = generer_ordre_virement(self.periode)
        fichier = fichier_virement_paie_simt(ordre)
        ligne = fichier['lignes'][1]
        # Le champ montant (15 car, numérique) contient le montant en
        # centimes du bulletin, jamais en dur. Offsets du gabarit :
        # type(1) + rib(24) + nom(26) = 51 -> montant(15) = [51:66].
        montant_centimes_attendu = int(b1.net_a_payer * 100)
        champ_montant = ligne[51:66]
        self.assertEqual(int(champ_montant), montant_centimes_attendu)
