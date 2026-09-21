"""Tests NTPAY20 — Registre annuel des rémunérations (obligation légale).

Couvre : le recoupement EXACT avec ``CumulAnnuel`` (aucun montant recalculé),
la présence de tous les salariés rémunérés dans l'année et l'absence de ceux
qui ne l'ont pas été, l'année filtrante, le rendu HTML, l'endpoint (400 sans
année) et l'isolation société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie import builders
from apps.paie.models import CumulAnnuel, PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    recalculer_cumul_annuel,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class RegistreRemunerationsTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay20')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, nom, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom=nom, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)

    def _paye(self, profil, periode=None):
        valider_bulletin(generer_bulletin(profil, periode or self.periode))
        return recalculer_cumul_annuel(profil, (periode or self.periode).annee)

    def test_cumuls_exacts_recoupes_avec_cumulannuel(self):
        profil = self._profil('A1', 'Bennani')
        cumul = self._paye(profil)
        registre = builders.registre_remunerations_context(self.co, 2026)
        self.assertEqual(registre['nombre_salaries'], 1)
        ligne = registre['lignes'][0]
        self.assertEqual(ligne['matricule'], 'A1')
        self.assertEqual(ligne['brut'], cumul.brut)
        self.assertEqual(ligne['net_a_payer'], cumul.net_a_payer)
        self.assertEqual(ligne['ir'], cumul.ir)
        self.assertEqual(ligne['cnss_salariale'], cumul.cnss_salariale)
        self.assertEqual(ligne['amo_salariale'], cumul.amo_salariale)
        self.assertEqual(ligne['nombre_bulletins'], cumul.nombre_bulletins)

    def test_totaux_egalent_la_somme_des_cumuls(self):
        self._paye(self._profil('B1', 'Alaoui'))
        self._paye(self._profil('B2', 'Cherkaoui', Decimal('16000')))
        registre = builders.registre_remunerations_context(self.co, 2026)
        self.assertEqual(registre['nombre_salaries'], 2)
        for champ in ('brut', 'net_a_payer', 'ir', 'cnss_salariale',
                      'amo_salariale'):
            self.assertEqual(
                registre['totaux'][champ],
                sum((Decimal(getattr(c, champ))
                     for c in CumulAnnuel.objects.filter(
                         company=self.co, annee=2026)), Decimal('0')),
                champ)

    def test_salarie_non_remunere_dans_l_annee_est_absent(self):
        self._paye(self._profil('C1', 'Payé'))
        self._profil('C2', 'JamaisPayé')  # aucun bulletin, aucun cumul
        registre = builders.registre_remunerations_context(self.co, 2026)
        matricules = {ligne['matricule'] for ligne in registre['lignes']}
        self.assertEqual(matricules, {'C1'})

    def test_annee_filtrante(self):
        profil = self._profil('D1', 'Année')
        self._paye(profil)
        autre_annee = PeriodePaie.objects.create(
            company=self.co, annee=2025, mois=12)
        self._paye(profil, autre_annee)
        self.assertEqual(
            builders.registre_remunerations_context(
                self.co, 2025)['nombre_salaries'], 1)
        self.assertEqual(
            builders.registre_remunerations_context(
                self.co, 2024)['nombre_salaries'], 0)

    def test_rendu_html(self):
        profil = self._profil('E1', 'Bennani')
        cumul = self._paye(profil)
        registre = builders.registre_remunerations_context(self.co, 2026)
        html = builders.render_registre_remunerations_html(
            registre, builders.employeur_context(self.co),
            today=date(2027, 1, 15))
        self.assertIn('Registre annuel des rémunérations — 2026', html)
        self.assertIn('Bennani', html)
        self.assertIn('E1', html)
        self.assertIn(builders._fmt(cumul.brut), html)
        self.assertIn(builders._fmt(cumul.net_a_payer), html)

    def test_rendu_html_annee_vide(self):
        registre = builders.registre_remunerations_context(self.co, 2024)
        html = builders.render_registre_remunerations_html(
            registre, builders.employeur_context(self.co),
            today=date(2025, 1, 15))
        self.assertIn('Aucune rémunération enregistrée', html)

    def test_isolation_societe(self):
        autre = make_company('ntpay20-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Zaoui', prenom='P')
        profil_autre = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('70000'), affilie_cnss=True,
            affilie_amo=True)
        valider_bulletin(generer_bulletin(profil_autre, periode_autre))
        recalculer_cumul_annuel(profil_autre, 2026)

        self._paye(self._profil('F1', 'Ici'))
        registre = builders.registre_remunerations_context(self.co, 2026)
        self.assertEqual(registre['nombre_salaries'], 1)
        self.assertEqual(registre['lignes'][0]['matricule'], 'F1')


class RegistreRemunerationsApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay20-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay20-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='A1', nom='N', prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True,
            affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, periode))
        recalculer_cumul_annuel(profil, 2026)
        self.url = '/api/django/paie/cumuls-annuels/registre-remunerations/'

    def test_json(self):
        rep = self.api.get(f'{self.url}?annee=2026')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data['annee'], 2026)
        self.assertEqual(rep.data['nombre_salaries'], 1)
        self.assertEqual(rep.data['lignes'][0]['matricule'], 'A1')

    def test_sans_annee_est_400(self):
        rep = self.api.get(self.url)
        self.assertEqual(rep.status_code, 400)

    def test_annee_invalide_est_400(self):
        rep = self.api.get(f'{self.url}?annee=abc')
        self.assertEqual(rep.status_code, 400)
