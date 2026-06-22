"""Tests PAIE7–PAIE12 — catalogue standard, profils, périodes, calcul bulletin.

Couvre :
* PAIE7  — seed idempotent du catalogue de rubriques standard (transport,
  panier, ancienneté, CIMR…).
* PAIE8  — ProfilPaie OneToOne→rh.DossierEmploye, société serveur, isolation,
  validation cross-app de l'employé.
* PAIE9  — RubriqueEmploye récurrente par profil.
* PAIE10 — PeriodePaie : cycle de statuts strictement progressif.
* PAIE11 — ElementVariable + import RH (inerte tant que RH n'expose rien).
* PAIE12 — moteur calculer_bulletin (brut/CNSS/AMO/IR/net).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.paie.models import (
    ElementVariable,
    PeriodePaie,
    ProfilPaie,
    Rubrique,
    RubriqueEmploye,
)
from apps.paie.services import (
    RUBRIQUES_DEFAUT,
    RUBRIQUES_STANDARD,
    TransitionPeriodeInterdite,
    calculer_bulletin,
    changer_statut,
    ensure_defaults,
    ensure_rubriques_standard,
    importer_elements_rh,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_dossier(company, matricule='M1', nom='Alami', prenom='Sami'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


# ── PAIE7 — Catalogue standard ─────────────────────────────────────────────

class CatalogueStandardTests(TestCase):
    def setUp(self):
        self.co = make_company('paie-cat-a', 'A')
        self.user = make_user(self.co, 'paie-cat-a')

    def test_seed_standard_idempotent_et_complet(self):
        api = auth(self.user)
        resp = api.post(
            '/api/django/paie/rubriques/seed-standard/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        total = len(RUBRIQUES_DEFAUT) + len(RUBRIQUES_STANDARD)
        self.assertEqual(resp.data['rubriques'], total)
        self.assertEqual(
            Rubrique.objects.filter(company=self.co).count(), total)
        # Rubriques marocaines standard présentes.
        for code in ('TRANSPORT', 'PANIER', 'ANCIENNETE', 'CIMR'):
            self.assertTrue(
                Rubrique.objects.filter(company=self.co, code=code).exists(),
                code)
        # Re-seed : aucun doublon.
        resp2 = api.post(
            '/api/django/paie/rubriques/seed-standard/', {}, format='json')
        self.assertEqual(resp2.data['rubriques'], 0)
        self.assertEqual(
            Rubrique.objects.filter(company=self.co).count(), total)

    def test_transport_panier_non_imposables(self):
        ensure_rubriques_standard(self.co)
        transport = Rubrique.objects.get(company=self.co, code='TRANSPORT')
        self.assertFalse(transport.imposable)
        self.assertFalse(transport.soumis_cnss)
        anciennete = Rubrique.objects.get(company=self.co, code='ANCIENNETE')
        self.assertTrue(anciennete.imposable)

    def test_seed_standard_never_overwrites_edited(self):
        edited = Rubrique.objects.create(
            company=self.co, code='TRANSPORT', libelle='Mon transport édité',
            montant_fixe=Decimal('400'))
        ensure_rubriques_standard(self.co)
        edited.refresh_from_db()
        self.assertEqual(edited.libelle, 'Mon transport édité')


# ── PAIE8 — ProfilPaie ─────────────────────────────────────────────────────

class ProfilPaieTests(TestCase):
    BASE = '/api/django/paie/profils/'

    def setUp(self):
        self.co_a = make_company('paie-prof-a', 'A')
        self.co_b = make_company('paie-prof-b', 'B')
        self.user_a = make_user(self.co_a, 'paie-prof-a')
        self.user_b = make_user(self.co_b, 'paie-prof-b')
        self.dossier_a = make_dossier(self.co_a, 'A1')
        self.dossier_b = make_dossier(self.co_b, 'B1')

    def _payload(self, employe):
        return {
            'employe': employe.id,
            'type_remuneration': 'mensuel',
            'salaire_base': '8000.00',
            'affilie_cnss': True,
            'affilie_amo': True,
            'rib': '0123456789',
            'banque': 'Attijariwafa',
        }

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.dossier_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ProfilPaie.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertNotIn('company', resp.data)

    def test_employe_autre_societe_refuse(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.dossier_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_isolation(self):
        ProfilPaie.objects.create(
            company=self.co_a, employe=self.dossier_a, salaire_base=5000)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'paie-prof-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_onetoone_unique(self):
        ProfilPaie.objects.create(
            company=self.co_a, employe=self.dossier_a, salaire_base=5000)
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.dossier_a), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ── PAIE9 — RubriqueEmploye ────────────────────────────────────────────────

class RubriqueEmployeTests(TestCase):
    BASE = '/api/django/paie/rubriques-employe/'

    def setUp(self):
        self.co = make_company('paie-re-a', 'A')
        self.user = make_user(self.co, 'paie-re-a')
        self.dossier = make_dossier(self.co, 'RE1')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier, salaire_base=7000)
        ensure_rubriques_standard(self.co)
        self.transport = Rubrique.objects.get(company=self.co, code='TRANSPORT')

    def test_create_recurrente(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'profil': self.profil.id,
            'rubrique': self.transport.id,
            'montant': '500.00',
            'actif': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = RubriqueEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co)
        self.assertEqual(obj.montant, Decimal('500.00'))

    def test_unique_profil_rubrique(self):
        RubriqueEmploye.objects.create(
            company=self.co, profil=self.profil, rubrique=self.transport)
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'profil': self.profil.id, 'rubrique': self.transport.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ── PAIE10 — PeriodePaie cycle de statuts ──────────────────────────────────

class PeriodePaieTests(TestCase):
    BASE = '/api/django/paie/periodes/'

    def setUp(self):
        self.co = make_company('paie-per-a', 'A')
        self.user = make_user(self.co, 'paie-per-a')

    def test_create_defaut_brouillon(self):
        api = auth(self.user)
        resp = api.post(
            self.BASE, {'annee': 2026, 'mois': 6}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'brouillon')

    def test_changer_statut_avance(self):
        periode = PeriodePaie.objects.create(company=self.co, annee=2026, mois=6)
        api = auth(self.user)
        url = f'{self.BASE}{periode.id}/changer-statut/'
        resp = api.post(url, {'statut': 'calculee'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'calculee')

    def test_retour_arriere_interdit(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7,
            statut=PeriodePaie.STATUT_VALIDEE)
        api = auth(self.user)
        url = f'{self.BASE}{periode.id}/changer-statut/'
        resp = api.post(url, {'statut': 'brouillon'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_cloture_pose_date(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=8,
            statut=PeriodePaie.STATUT_VALIDEE)
        changer_statut(periode, PeriodePaie.STATUT_CLOTUREE)
        periode.refresh_from_db()
        self.assertEqual(periode.statut, PeriodePaie.STATUT_CLOTUREE)
        self.assertIsNotNone(periode.date_cloture)

    def test_statut_inconnu_leve(self):
        periode = PeriodePaie.objects.create(company=self.co, annee=2026, mois=9)
        with self.assertRaises(TransitionPeriodeInterdite):
            changer_statut(periode, 'inconnu')

    def test_unique_annee_mois(self):
        PeriodePaie.objects.create(company=self.co, annee=2026, mois=6)
        api = auth(self.user)
        resp = api.post(self.BASE, {'annee': 2026, 'mois': 6}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ── PAIE11 — ElementVariable + import RH ───────────────────────────────────

class ElementVariableTests(TestCase):
    def setUp(self):
        self.co = make_company('paie-ev-a', 'A')
        self.user = make_user(self.co, 'paie-ev-a')
        self.dossier = make_dossier(self.co, 'EV1')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier, salaire_base=6000)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_create_element_force_company(self):
        api = auth(self.user)
        resp = api.post('/api/django/paie/elements-variables/', {
            'periode': self.periode.id,
            'profil': self.profil.id,
            'type': 'prime',
            'libelle': 'Prime exceptionnelle',
            'montant': '1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ElementVariable.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co)
        self.assertEqual(obj.source, 'manuel')

    def test_import_rh_inerte_sans_donnees(self):
        # Tant que RH n'expose pas d'heures/absences, l'import ne plante pas.
        importes = importer_elements_rh(self.periode)
        self.assertEqual(importes, 0)

    def test_import_rh_refuse_hors_brouillon(self):
        self.periode.statut = PeriodePaie.STATUT_CALCULEE
        self.periode.save(update_fields=['statut'])
        with self.assertRaises(TransitionPeriodeInterdite):
            importer_elements_rh(self.periode)

    def test_import_rh_preserve_saisie_manuelle(self):
        manuel = ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type='prime', montant=500, source=ElementVariable.SOURCE_MANUEL)
        importer_elements_rh(self.periode)
        self.assertTrue(
            ElementVariable.objects.filter(id=manuel.id).exists())


# ── PAIE12 — Moteur de calcul du bulletin ──────────────────────────────────

class CalculBulletinTests(TestCase):
    def setUp(self):
        self.co = make_company('paie-calc-a', 'A')
        self.user = make_user(self.co, 'paie-calc-a')
        ensure_defaults(self.co)  # paramètres + barème IR 2026
        self.dossier = make_dossier(self.co, 'C1')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier, salaire_base=Decimal('10000'),
            affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_cnss_plafonnee(self):
        res = calculer_bulletin(self.profil, self.periode)
        # CNSS = 4.48% × min(10000, 6000) = 4.48% × 6000 = 268.80
        self.assertEqual(res['cnss_salariale'], Decimal('268.80'))

    def test_amo_non_plafonnee(self):
        res = calculer_bulletin(self.profil, self.periode)
        # AMO = 2.26% × 10000 = 226.00
        self.assertEqual(res['amo_salariale'], Decimal('226.00'))

    def test_brut_inclut_primes_variables(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type='prime', montant=Decimal('2000'),
            source=ElementVariable.SOURCE_MANUEL)
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('12000.00'))

    def test_net_a_payer_inferieur_brut(self):
        res = calculer_bulletin(self.profil, self.periode)
        self.assertLess(res['net_a_payer'], res['brut'])
        self.assertGreater(res['net_a_payer'], Decimal('0'))

    def test_ir_positif(self):
        res = calculer_bulletin(self.profil, self.periode)
        self.assertGreater(res['ir'], Decimal('0'))

    def test_retenue_avance_reduit_net(self):
        sans = calculer_bulletin(self.profil, self.periode)['net_a_payer']
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type='retenue', montant=Decimal('1500'),
            source=ElementVariable.SOURCE_MANUEL)
        avec = calculer_bulletin(self.profil, self.periode)['net_a_payer']
        self.assertEqual(sans - avec, Decimal('1500.00'))

    def test_endpoint_bulletin(self):
        api = auth(self.user)
        url = (f'/api/django/paie/periodes/{self.periode.id}/bulletin/'
               f'?profil={self.profil.id}')
        resp = api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('net_a_payer', resp.data)
        self.assertIn('lignes', resp.data)

    def test_endpoint_bulletin_profil_requis(self):
        api = auth(self.user)
        resp = api.get(f'/api/django/paie/periodes/{self.periode.id}/bulletin/')
        self.assertEqual(resp.status_code, 400, resp.data)
