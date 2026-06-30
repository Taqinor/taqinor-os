"""Tests PAIE25 — Provision pour congés payés (consomme les soldes RH).

Couvre :
* ``taux_journalier_profil`` — dérivation du taux journalier selon le type de
  rémunération (mensuel / journalier / forfait / horaire).
* ``provision_conges_payes`` — provision = jours CP acquis × taux journalier ;
  surcharge du nombre de jours ; 0 quand taux nul.
* ``solde_conge_disponible`` — lecture du solde de congés RH par string-FK
  (report + acquis − pris), cadrée société, 0 si absent.
* ``calculer_bulletin`` — la provision apparaît dans le snapshot et N'AFFECTE
  PAS le net à payer (charge patronale informative).
* Multi-tenant — isolation société sur la lecture du solde RH.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    JOURS_CP_ACQUIS_PAR_MOIS,
    calculer_bulletin,
    ensure_defaults,
    provision_conges_payes,
    solde_conge_disponible,
    taux_journalier_profil,
)
from apps.rh.models import DossierEmploye, SoldeConge


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_dossier(company, matricule='E1'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='CP')


def make_profil(company, dossier, salaire_base=Decimal('10000'),
                type_rem=ProfilPaie.TYPE_MENSUEL):
    return ProfilPaie.objects.create(
        company=company, employe=dossier,
        type_remuneration=type_rem, salaire_base=salaire_base,
        affilie_cnss=True, affilie_amo=True)


class TauxJournalierTests(TestCase):
    def setUp(self):
        self.co = make_company('cp-tj')
        self.dossier = make_dossier(self.co)

    def test_mensuel_divise_par_jours_norme(self):
        profil = make_profil(self.co, self.dossier, Decimal('2600'))
        # 2600 / 26 jours = 100/jour.
        self.assertEqual(taux_journalier_profil(profil), Decimal('100.00'))

    def test_journalier_taux_direct(self):
        profil = make_profil(
            self.co, self.dossier, Decimal('150'),
            type_rem=ProfilPaie.TYPE_JOURNALIER)
        self.assertEqual(taux_journalier_profil(profil), Decimal('150.00'))

    def test_horaire_ramene_au_jour(self):
        profil = make_profil(
            self.co, self.dossier, Decimal('20'),
            type_rem=ProfilPaie.TYPE_HORAIRE)
        # 20 MAD/h × 191 h = 3820 mensuel / 26 j ≈ 146,92.
        self.assertEqual(taux_journalier_profil(profil), Decimal('146.92'))


class ProvisionTests(TestCase):
    def setUp(self):
        self.co = make_company('cp-prov')
        self.dossier = make_dossier(self.co)
        self.profil = make_profil(self.co, self.dossier, Decimal('2600'))

    def test_provision_standard(self):
        # 1,5 j × 100/jour = 150.
        prov = provision_conges_payes(self.profil, None)
        self.assertEqual(prov, Decimal('150.00'))
        self.assertEqual(JOURS_CP_ACQUIS_PAR_MOIS, Decimal('1.5'))

    def test_provision_surcharge_jours(self):
        prov = provision_conges_payes(
            self.profil, None, jours_acquis=Decimal('0.75'))
        self.assertEqual(prov, Decimal('75.00'))

    def test_provision_zero_si_taux_nul(self):
        profil = make_profil(
            make_company('cp-prov2'), make_dossier(make_company('cp-prov2')),
            Decimal('0'))
        self.assertEqual(provision_conges_payes(profil, None), Decimal('0.00'))


class SoldeCongeLectureTests(TestCase):
    def setUp(self):
        self.co = make_company('cp-solde')
        self.autre = make_company('cp-solde-autre')
        self.dossier = make_dossier(self.co)

    def test_lit_solde_disponible(self):
        SoldeConge.objects.create(
            company=self.co, employe=self.dossier, annee=2026,
            acquis=Decimal('18'), report=Decimal('3'), pris=Decimal('5'))
        self.assertEqual(
            solde_conge_disponible(self.co, self.dossier.id, 2026),
            Decimal('16.00'))

    def test_zero_si_absent(self):
        self.assertEqual(
            solde_conge_disponible(self.co, self.dossier.id, 2026),
            Decimal('0'))

    def test_isolation_societe(self):
        SoldeConge.objects.create(
            company=self.co, employe=self.dossier, annee=2026,
            acquis=Decimal('18'))
        # Lu depuis une autre société → 0 (jamais de fuite cross-tenant).
        self.assertEqual(
            solde_conge_disponible(self.autre, self.dossier.id, 2026),
            Decimal('0'))


class BulletinProvisionTests(TestCase):
    def setUp(self):
        self.co = make_company('cp-bull')
        ensure_defaults(self.co)
        self.dossier = make_dossier(self.co)
        self.profil = make_profil(self.co, self.dossier, Decimal('2600'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_provision_dans_snapshot_sans_toucher_net(self):
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['provision_conges'], Decimal('150.00'))
        # Le net à payer ne dépend que des retenues salariales (CNSS/AMO/IR) :
        # la provision patronale ne le diminue jamais.
        net_attendu = (
            res['brut'] - res['cnss_salariale'] - res['amo_salariale']
            - res['cimr_salariale'] - res['ir'] - res['retenues']
        )
        self.assertEqual(res['net_a_payer'], net_attendu)
