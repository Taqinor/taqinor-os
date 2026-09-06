"""Tests AUD710 — `valide_par_fondateur` devient un signal réel + un seul
propriétaire du taux AMO patronal.

Constat d'audit : `valide_par_fondateur` n'était lu QUE par le seed, l'admin,
le sérialiseur et les tests — jamais par `calculer_bulletin`,
`declaration_cnss` ni `generer_ordre_virement`. Un `ParametrePaie` jamais
confirmé calculait donc des bulletins RÉELS sans le moindre signal (seul un
badge cosmétique existait à l'écran). Et le taux AMO patronal avait TROIS
propriétaires : le défaut du modèle, la table de semis, et un littéral recopié
dans `selectors.taux_charges_patronales`.

La valeur du taux (2,26 % codé vs 4,11 % de référence usuelle) reste une
QUESTION FONDATEUR/COMPTABLE : aucun test ici ne la tranche — ils vérifient
seulement qu'elle n'a qu'un propriétaire et qu'elle est visible/éditable.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ParametrePaie, PeriodePaie, ProfilPaie
from apps.paie.selectors import taux_charges_patronales
from apps.paie.services import (
    PARAMETRES_DEFAUT_2026,
    avertissements_parametre_paie,
    avertissements_periode,
    calculer_bulletin,
    declaration_cnss,
    ensure_defaults,
    generer_bulletin,
    generer_ordre_virement,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class AvertissementParametreNonValideTests(TestCase):
    def setUp(self):
        self.co = make_company('aud710')
        # ensure_defaults provisionne AVEC valide_par_fondateur=False.
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='P1', nom='Nom', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            affilie_cnss=True, affilie_amo=True, numero_cnss='987654321')

    def _valider_parametres(self):
        ParametrePaie.objects.filter(company=self.co).update(
            valide_par_fondateur=True)

    def test_etat_par_defaut_du_seed_est_non_valide(self):
        """Prémisse du constat : le semis part toujours à False."""
        parametre = ParametrePaie.objects.filter(company=self.co).first()
        self.assertIsNotNone(parametre)
        self.assertFalse(parametre.valide_par_fondateur)

    def test_calculer_bulletin_avertit(self):
        resultat = calculer_bulletin(self.profil, self.periode)
        self.assertTrue(resultat['avertissements'])
        self.assertIn('NON VALIDÉS', resultat['avertissements'][0])

    def test_calculer_bulletin_silencieux_une_fois_valide(self):
        self._valider_parametres()
        resultat = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(resultat['avertissements'], [])
        # Le calcul lui-même n'est pas modifié par la validation.
        self.assertGreater(resultat['net_a_payer'], Decimal('0'))

    def test_declaration_cnss_avertit(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        decl = declaration_cnss(self.periode)
        self.assertTrue(decl['avertissements'])
        self._valider_parametres()
        self.assertEqual(declaration_cnss(self.periode)['avertissements'], [])

    def test_generer_ordre_virement_journalise_l_avertissement(self):
        with self.assertLogs('apps.paie.services', level='WARNING') as journal:
            generer_ordre_virement(self.periode)
        self.assertTrue(
            any('non validés' in ligne.lower() for ligne in journal.output),
            journal.output)

    def test_panneau_pre_run_porte_un_bloquant(self):
        """ZPAI2 — le seul écran qui dit « à corriger avant de payer »."""
        items = avertissements_periode(self.periode)
        bloquants = [a for a in items
                     if a['type'] == 'parametres_non_valides']
        self.assertEqual(len(bloquants), 1)
        self.assertEqual(bloquants[0]['gravite'], 'bloquant')
        self._valider_parametres()
        self.assertFalse([a for a in avertissements_periode(self.periode)
                          if a['type'] == 'parametres_non_valides'])

    def test_sans_parametre_du_tout_avertit_aussi(self):
        autre = make_company('aud710-vide')
        messages = avertissements_parametre_paie(autre, date(2026, 6, 1))
        self.assertEqual(len(messages), 1)
        self.assertIn('Aucun paramètre social', messages[0])


class TauxAmoPatronalProprietaireUniqueTests(TestCase):
    def setUp(self):
        self.co = make_company('aud710-taux')

    def test_selecteur_lit_le_parametre_reel(self):
        ensure_defaults(self.co)
        ParametrePaie.objects.filter(company=self.co).update(
            taux_amo_patronal=Decimal('4.11'))
        parametre = ParametrePaie.objects.filter(company=self.co).first()
        attendu = (
            Decimal(parametre.taux_cnss_patronal)
            + Decimal(parametre.taux_amo_patronal)
            + Decimal(parametre.taux_allocations_familiales)
            + Decimal(parametre.taux_formation_pro)) / Decimal('100')
        self.assertEqual(taux_charges_patronales(self.co), attendu)

    def test_repli_sans_parametre_lit_les_defauts_du_modele(self):
        """Aucun littéral recopié : le repli vient des défauts de champ."""
        champs = ('taux_cnss_patronal', 'taux_amo_patronal',
                  'taux_allocations_familiales', 'taux_formation_pro')
        attendu = sum(
            (Decimal(ParametrePaie._meta.get_field(c).default) for c in champs),
            Decimal('0')) / Decimal('100')
        self.assertEqual(taux_charges_patronales(self.co), attendu)

    def test_defaut_du_modele_et_table_de_semis_concordent(self):
        """Les deux propriétaires restants ne peuvent plus diverger en silence."""
        for champ in ('taux_cnss_salarial', 'taux_cnss_patronal',
                      'taux_amo_salarial', 'taux_amo_patronal',
                      'taux_allocations_familiales', 'taux_formation_pro',
                      'plafond_cnss'):
            self.assertEqual(
                Decimal(ParametrePaie._meta.get_field(champ).default),
                Decimal(PARAMETRES_DEFAUT_2026[champ]),
                f'{champ} : défaut du modèle ≠ valeur provisionnée.')
