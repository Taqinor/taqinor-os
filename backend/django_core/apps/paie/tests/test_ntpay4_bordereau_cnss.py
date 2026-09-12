"""Tests NTPAY4 — Télépaiement CNSS : bordereau de paiement + fichier.

Couvre : les totaux par organisme = somme des lignes cotisations des bulletins
VALIDÉS (un brouillon est exclu), la date limite au 10 du mois suivant, la
référence du dépôt BDS (vide tant qu'aucun dépôt), le fichier de télépaiement
à longueurs fixes, l'endpoint (JSON + ``?export=fichier``) et l'isolation
société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    GABARIT_TELEPAIEMENT_CNSS_ENTETE,
    GABARIT_TELEPAIEMENT_CNSS_LIGNE,
    bordereau_paiement_cnss,
    deposer_bds_principal,
    ensure_defaults,
    fichier_telepaiement_cnss,
    generer_bulletin,
    livre_de_paie,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class BordereauCnssTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay4')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)

    def _bulletin_valide(self, matricule, salaire=Decimal('10000')):
        bulletin = generer_bulletin(self._profil(matricule, salaire),
                                    self.periode)
        valider_bulletin(bulletin)
        return bulletin

    def test_totaux_par_organisme_egalent_le_livre_de_paie(self):
        self._bulletin_valide('A1')
        self._bulletin_valide('A2', Decimal('7000'))
        bordereau = bordereau_paiement_cnss(self.periode)
        totaux = livre_de_paie(self.periode)['totaux']
        par_code = {o['code']: o for o in bordereau['organismes']}

        self.assertEqual(par_code['cnss']['salarial'],
                         totaux['cnss_salariale'])
        self.assertEqual(par_code['cnss']['patronal'],
                         totaux['cnss_patronale'])
        self.assertEqual(par_code['amo']['salarial'], totaux['amo_salariale'])
        self.assertEqual(par_code['amo']['patronal'], totaux['amo_patronale'])
        self.assertEqual(par_code['allocations_familiales']['total'],
                         totaux['allocations_familiales'])
        self.assertEqual(par_code['formation_professionnelle']['total'],
                         totaux['formation_professionnelle'])
        self.assertEqual(
            bordereau['total_general'],
            sum(o['total'] for o in bordereau['organismes']))
        self.assertEqual(bordereau['nombre_salaries'], 2)

    def test_brouillon_exclu(self):
        self._bulletin_valide('B1')
        generer_bulletin(self._profil('B2'), self.periode)  # reste brouillon
        bordereau = bordereau_paiement_cnss(self.periode)
        self.assertEqual(bordereau['nombre_salaries'], 1)

    def test_date_limite_le_10_du_mois_suivant(self):
        self._bulletin_valide('C1')
        bordereau = bordereau_paiement_cnss(self.periode)
        self.assertEqual(bordereau['date_limite'], date(2026, 7, 10))

    def test_date_limite_bascule_d_annee_en_decembre(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=12)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='D1', nom='N', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), affilie_cnss=True, affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, periode))
        self.assertEqual(
            bordereau_paiement_cnss(periode)['date_limite'],
            date(2027, 1, 10))

    def test_reference_bds_vide_sans_depot_puis_renseignee(self):
        self._bulletin_valide('E1')
        self.assertEqual(bordereau_paiement_cnss(self.periode)['reference_bds'],
                         '')
        depot = deposer_bds_principal(self.periode)
        bordereau = bordereau_paiement_cnss(self.periode)
        self.assertEqual(bordereau['reference_bds'], f'BDS-{depot.id}')
        self.assertIsNotNone(bordereau['date_depot_bds'])

    def test_fichier_telepaiement_longueurs_fixes(self):
        self._bulletin_valide('F1')
        fichier = fichier_telepaiement_cnss(self.periode)
        longueur_entete = sum(
            lg for _c, lg, _r in GABARIT_TELEPAIEMENT_CNSS_ENTETE)
        longueur_ligne = sum(
            lg for _c, lg, _r in GABARIT_TELEPAIEMENT_CNSS_LIGNE)
        self.assertEqual(len(fichier['lignes']), 5)  # en-tête + 4 organismes
        self.assertEqual(len(fichier['lignes'][0]), longueur_entete)
        self.assertTrue(fichier['lignes'][0].startswith('E'))
        for ligne in fichier['lignes'][1:]:
            self.assertEqual(len(ligne), longueur_ligne)
            self.assertTrue(ligne.startswith('D'))
        self.assertEqual(fichier['nb_lignes'], 4)

    def test_isolation_societe(self):
        autre = make_company('ntpay4-autre')
        ensure_defaults(autre)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P')
        profil = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('50000'),
            affilie_cnss=True, affilie_amo=True)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        valider_bulletin(generer_bulletin(profil, periode_autre))

        self._bulletin_valide('G1')
        bordereau = bordereau_paiement_cnss(self.periode)
        self.assertEqual(bordereau['nombre_salaries'], 1)
        par_code = {o['code']: o for o in bordereau['organismes']}
        self.assertEqual(
            par_code['cnss']['salarial'],
            livre_de_paie(self.periode)['totaux']['cnss_salariale'])


class BordereauCnssApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay4-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay4-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='A1', nom='N', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            affilie_cnss=True, affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, self.periode))

    def test_endpoint_json(self):
        rep = self.api.get(
            f'/api/django/paie/periodes/{self.periode.id}/bordereau-cnss/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data['organismes']), 4)
        self.assertGreater(Decimal(str(rep.data['total_general'])), 0)

    def test_endpoint_fichier(self):
        rep = self.api.get(
            f'/api/django/paie/periodes/{self.periode.id}/bordereau-cnss/'
            '?export=fichier')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data['lignes']), 5)
