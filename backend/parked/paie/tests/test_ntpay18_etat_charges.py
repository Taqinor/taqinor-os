"""Tests NTPAY18 — État des charges sociales et fiscales (document de synthèse).

Couvre : les CINQ organismes (CNSS, AMO, IR, CIMR, mutuelle) dont les totaux
égalent EXACTEMENT la somme des lignes de cotisation des bulletins VALIDÉS,
l'exclusion des brouillons, les charges annexes recouvrées par la CNSS
(incluses dans le total à verser), l'absence de taux inventé pour CIMR et
mutuelle, la non-régression de l'état XPAI5 existant, le rendu HTML et
l'isolation société.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie import builders
from apps.paie.models import (
    AdhesionMutuelle, LigneBulletin, PeriodePaie, ProfilPaie, RegimeMutuelle,
)
from apps.paie.services import (
    etat_charges,
    etat_des_charges,
    ensure_defaults,
    generer_bulletin,
    livre_de_paie,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class EtatChargesTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay18')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Prévoyance groupe',
            mode=RegimeMutuelle.MODE_POURCENTAGE,
            part_salariale=Decimal('1'), part_patronale=Decimal('2'))

    def _profil(self, matricule, salaire=Decimal('10000'), *,
                cimr=False, mutuelle=False):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True,
            affilie_cimr=cimr,
            taux_cimr_salarial=Decimal('6') if cimr else Decimal('0'))
        if mutuelle:
            AdhesionMutuelle.objects.create(
                company=self.co, profil=profil, regime=self.regime,
                date_debut=date(2026, 1, 1))
        return profil

    def _valide(self, profil):
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)
        return bulletin

    def test_cinq_organismes(self):
        self._valide(self._profil('A1'))
        etat = etat_charges(self.periode)
        codes = [o['code'] for o in etat['organismes']]
        self.assertEqual(codes, ['cnss', 'amo', 'ir', 'cimr', 'mutuelle'])
        self.assertEqual(len(etat['organismes']), 5)

    def test_totaux_egalent_les_bulletins_valides(self):
        self._valide(self._profil('B1'))
        self._valide(self._profil('B2', Decimal('18000'), cimr=True,
                                  mutuelle=True))
        etat = etat_charges(self.periode)
        totaux = livre_de_paie(self.periode)['totaux']
        par_code = {o['code']: o for o in etat['organismes']}

        self.assertEqual(par_code['cnss']['salarial'],
                         totaux['cnss_salariale'])
        self.assertEqual(par_code['cnss']['patronal'],
                         totaux['cnss_patronale'])
        self.assertEqual(par_code['amo']['salarial'], totaux['amo_salariale'])
        self.assertEqual(par_code['amo']['patronal'], totaux['amo_patronale'])
        self.assertEqual(par_code['ir']['salarial'], totaux['ir'])
        self.assertEqual(par_code['cimr']['salarial'],
                         totaux['cimr_salariale'])

        # La mutuelle n'a AUCUN champ de bulletin : elle vient des lignes.
        lignes_sal = sum(
            (ligne.montant for ligne in LigneBulletin.objects.filter(
                company=self.co, bulletin__periode=self.periode,
                code='MUTUELLE_SAL')), Decimal('0'))
        self.assertEqual(par_code['mutuelle']['salarial'], lignes_sal)
        self.assertGreater(par_code['mutuelle']['salarial'], 0)

        for organisme in etat['organismes']:
            self.assertEqual(
                organisme['total'],
                organisme['salarial'] + organisme['patronal'])

    def test_les_totaux_egalent_les_lignes_de_cotisation(self):
        self._valide(self._profil('C1'))
        self._valide(self._profil('C2', Decimal('16000')))
        etat = etat_charges(self.periode)
        par_code = {o['code']: o for o in etat['organismes']}

        def somme(code):
            return sum(
                (ligne.montant for ligne in LigneBulletin.objects.filter(
                    company=self.co, bulletin__periode=self.periode,
                    code=code)), Decimal('0'))

        self.assertEqual(par_code['cnss']['salarial'], somme('CNSS_SAL'))
        self.assertEqual(par_code['amo']['salarial'], somme('AMO_SAL'))
        self.assertEqual(par_code['ir']['salarial'], somme('IR'))

    def test_brouillon_exclu(self):
        self._valide(self._profil('D1'))
        generer_bulletin(self._profil('D2'), self.periode)  # reste brouillon
        etat = etat_charges(self.periode)
        self.assertEqual(etat['nombre_salaries'], 1)
        par_code = {o['code']: o for o in etat['organismes']}
        self.assertEqual(par_code['cnss']['salarial'],
                         livre_de_paie(self.periode)['totaux']['cnss_salariale'])

    def test_charges_annexes_comptent_dans_le_total_a_verser(self):
        self._valide(self._profil('E1'))
        etat = etat_charges(self.periode)
        codes = [a['code'] for a in etat['charges_annexes']]
        self.assertEqual(
            codes, ['allocations_familiales', 'formation_professionnelle'])
        annexes = sum(
            (a['patronal'] for a in etat['charges_annexes']), Decimal('0'))
        self.assertGreater(annexes, 0)
        organismes_pat = sum(
            (o['patronal'] for o in etat['organismes']), Decimal('0'))
        self.assertEqual(etat['total_patronal'], organismes_pat + annexes)
        self.assertEqual(
            etat['total_general'],
            etat['total_salarial'] + etat['total_patronal'])

    def test_aucun_taux_invente_pour_cimr_et_mutuelle(self):
        self._valide(self._profil('F1', cimr=True, mutuelle=True))
        par_code = {o['code']: o for o in etat_charges(self.periode)['organismes']}
        for code in ('cimr', 'mutuelle', 'ir'):
            self.assertIsNone(par_code[code]['taux_salarial'], code)
            self.assertIsNone(par_code[code]['taux_patronal'], code)
        # CNSS/AMO, eux, ont UN taux de société : il est affiché.
        self.assertIsNotNone(par_code['cnss']['taux_salarial'])
        self.assertIsNotNone(par_code['amo']['taux_patronal'])

    def test_etat_xpai5_inchange(self):
        """Non-régression : l'état à 3 postes garde exactement sa forme."""
        self._valide(self._profil('G1'))
        ancien = etat_des_charges(self.periode)
        self.assertEqual(
            [o['code'] for o in ancien['organismes']],
            ['cnss_amo', 'ir', 'cimr'])

    def test_rendu_html(self):
        self._valide(self._profil('H1', cimr=True, mutuelle=True))
        etat = etat_charges(self.periode)
        html = builders.render_etat_charges_html(
            etat, builders.employeur_context(self.co),
            today=date(2026, 7, 5))
        self.assertIn('État des charges sociales et fiscales', html)
        self.assertIn('06/2026', html)
        self.assertIn('CNSS', html)
        self.assertIn('Mutuelle', html)
        self.assertIn('Allocations familiales', html)
        self.assertIn(builders._fmt(etat['total_general']), html)
        # Les taux absents s'impriment « — », jamais une moyenne inventée.
        self.assertIn('—', html)

    def test_isolation_societe(self):
        autre = make_company('ntpay18-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='Z1', nom='Z', prenom='P')
        profil = ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('90000'), affilie_cnss=True,
            affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, periode_autre))

        self._valide(self._profil('I1'))
        etat = etat_charges(self.periode)
        self.assertEqual(etat['nombre_salaries'], 1)
        par_code = {o['code']: o for o in etat['organismes']}
        self.assertEqual(
            par_code['amo']['base'], Decimal('10000.00'))


class EtatChargesApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay18-api')
        ensure_defaults(self.co)
        self.user = User.objects.create_user(
            username='ntpay18-resp', password='x', company=self.co,
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
            salaire_base=Decimal('12000'), affilie_cnss=True,
            affilie_amo=True)
        valider_bulletin(generer_bulletin(profil, self.periode))
        self.url = (
            f'/api/django/paie/periodes/{self.periode.id}/etat-charges/')

    def test_json_par_defaut_reste_xpai5(self):
        rep = self.api.get(self.url)
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data['organismes']), 3)

    def test_json_detaille(self):
        rep = self.api.get(f'{self.url}?detail=1')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data['organismes']), 5)
        self.assertIn('charges_annexes', rep.data)
        self.assertIn('total_general', rep.data)

    def test_export_csv_inchange(self):
        rep = self.api.get(f'{self.url}?export=csv')
        self.assertEqual(rep.status_code, 200)
        self.assertIn('text/csv', rep['Content-Type'])

    def test_periode_d_une_autre_societe_invisible(self):
        autre = make_company('ntpay18-api-autre')
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        rep = self.api.get(
            f'/api/django/paie/periodes/{periode_autre.id}/etat-charges/'
            '?detail=1')
        self.assertEqual(rep.status_code, 404)
