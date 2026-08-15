"""Tests WIR243 — Rubriques récurrentes branchées au moteur de calcul.

``RubriqueEmploye`` (PAIE9) existait en CRUD + rattachement idempotent
(``ensure_rubriques_standard``/``appliquer_structure_a_profil``) sans jamais
être lue par ``calculer_bulletin`` : une « prime transport 500 MAD » rattachée
à un profil n'apparaissait jamais sur le bulletin. Couvre :

* une rubrique récurrente ACTIVE (gain, imposable) augmente brut ET
  brut_imposable du montant surchargé ;
* la surcharge ``montant`` prime sur ``montant_fixe`` de la rubrique
  catalogue ;
* une rubrique récurrente INACTIVE (``actif=False``) n'a aucun effet ;
* une fenêtre de dates (``date_fin`` dépassée) exclut la rubrique ;
* une rubrique de type retenue diminue le net sans toucher au brut imposable.
"""
from decimal import Decimal

from django.test import TestCase

from apps.paie.models import PeriodePaie, ProfilPaie, Rubrique, RubriqueEmploye
from apps.paie.services import calculer_bulletin, ensure_defaults
from apps.paie.tests.test_avantages import make_company, make_dossier, make_profil, make_rubrique


def make_periode(company, annee=2026, mois=6):
    return PeriodePaie.objects.create(company=company, annee=annee, mois=mois)


class RubriquesRecurrentesBulletinTests(TestCase):
    def setUp(self):
        self.co = make_company('wir243-rubriques-recurrentes')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co, matricule='WIR243-1')
        self.profil = make_profil(self.co, self.dossier, salaire_base=Decimal('8000'))
        self.periode = make_periode(self.co)

    def test_rubrique_recurrente_active_avec_surcharge_augmente_brut(self):
        rub = make_rubrique(self.co, 'TRANSPORT', imposable=True)
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub,
            montant=Decimal('500'), actif=True,
        )
        resultat = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(resultat['brut'], Decimal('8500.00'))
        self.assertEqual(resultat['brut_imposable'], Decimal('8500.00'))
        codes = [ligne['code'] for ligne in resultat['lignes']]
        self.assertIn('TRANSPORT', codes)

    def test_surcharge_montant_prime_sur_montant_fixe_catalogue(self):
        rub = Rubrique.objects.create(
            company=self.co, code='PRIME_X', libelle='Prime X',
            type=Rubrique.TYPE_GAIN, imposable=True, montant_fixe=Decimal('300'),
        )
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub,
            montant=Decimal('750'), actif=True,
        )
        resultat = calculer_bulletin(self.profil, self.periode)
        ligne = next(row for row in resultat['lignes'] if row['code'] == 'PRIME_X')
        self.assertEqual(ligne['montant'], Decimal('750.00'))

    def test_rubrique_desactivee_n_a_aucun_effet(self):
        rub = make_rubrique(self.co, 'PANIER', imposable=True)
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub,
            montant=Decimal('400'), actif=False,
        )
        resultat = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(resultat['brut'], Decimal('8000.00'))
        codes = [ligne['code'] for ligne in resultat['lignes']]
        self.assertNotIn('PANIER', codes)

    def test_fenetre_de_dates_expiree_exclut_la_rubrique(self):
        rub = make_rubrique(self.co, 'PRIME_TEMP', imposable=True)
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub,
            montant=Decimal('600'), actif=True,
            date_debut='2026-01-01', date_fin='2026-03-31',
        )
        # La période testée (juin 2026) est hors fenêtre.
        resultat = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(resultat['brut'], Decimal('8000.00'))

    def test_rubrique_retenue_diminue_le_net_sans_toucher_brut_imposable(self):
        rub = Rubrique.objects.create(
            company=self.co, code='RETENUE_X', libelle='Retenue X',
            type=Rubrique.TYPE_RETENUE,
        )
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=rub,
            montant=Decimal('200'), actif=True,
        )
        sans_retenue = calculer_bulletin(
            ProfilPaie.objects.create(
                company=self.co, employe=make_dossier(self.co, matricule='WIR243-2'),
                type_remuneration=ProfilPaie.TYPE_MENSUEL,
                salaire_base=Decimal('8000'), affilie_cnss=True, affilie_amo=True,
            ),
            self.periode,
        )
        avec_retenue = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(avec_retenue['brut'], sans_retenue['brut'])
        self.assertEqual(avec_retenue['brut_imposable'], sans_retenue['brut_imposable'])
        self.assertLess(avec_retenue['net_a_payer'], sans_retenue['net_a_payer'])
