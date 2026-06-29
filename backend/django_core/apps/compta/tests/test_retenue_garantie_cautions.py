"""Tests FG145 — Retenue de garantie (RG) & cautions bancaires sur marchés.

Couvre : le calcul de la RG retenue par taux (base × taux %, arrondi), la
référence auto-numérotée posée côté serveur, les transitions de statut
(``liberer`` / ``mainlevee``) avec leurs dates, le sélecteur d'échéances (RG et
cautions arrivant à maturité sous N jours, retards inclus), les filtres
``statut`` / ``type_caution``, l'isolation multi-société, la pose de
``company`` / ``montant`` côté serveur (jamais imposables) et le gate de rôle
(Admin/Responsable). Tout est additif et scopé société.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CautionBancaire, RetenueGarantie

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


# ── Retenue de garantie : service & calcul ────────────────────────────────
class RetenueGarantieServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg145-rg-svc', 'FG145 RG Svc')
        self.user = make_user(self.co, 'fg145-rg-svc-user')

    def test_montant_calcule_au_taux_defaut(self):
        # Base 100 000 × 10 % (défaut) = 10 000 retenu.
        rg = services.enregistrer_retenue_garantie(
            self.co, date_constitution=date(2026, 1, 10),
            base=Decimal('100000'), marche_ref='MARCHE-2026-01',
            tiers_nom='Maître Ouvrage', user=self.user)
        self.assertEqual(rg.taux, Decimal('10.00'))
        self.assertEqual(rg.montant, Decimal('10000.00'))
        self.assertEqual(rg.statut, RetenueGarantie.Statut.RETENUE)
        self.assertTrue(rg.reference.startswith('RG-'))
        self.assertEqual(rg.created_by, self.user)
        self.assertIsNone(rg.date_liberation)

    def test_montant_calcule_taux_explicite_et_arrondi(self):
        # Base 1 234,56 × 5 % = 61,728 → arrondi 61,73.
        rg = services.enregistrer_retenue_garantie(
            self.co, date_constitution=date(2026, 2, 1),
            base=Decimal('1234.56'), taux=Decimal('5'), user=self.user)
        self.assertEqual(rg.taux, Decimal('5'))
        self.assertEqual(rg.montant, Decimal('61.73'))

    def test_references_uniques_consecutives(self):
        r1 = services.enregistrer_retenue_garantie(
            self.co, date_constitution=date(2026, 1, 5), base=Decimal('1000'),
            user=self.user)
        r2 = services.enregistrer_retenue_garantie(
            self.co, date_constitution=date(2026, 1, 6), base=Decimal('1000'),
            user=self.user)
        self.assertNotEqual(r1.reference, r2.reference)

    def test_liberer_pose_statut_et_date(self):
        rg = services.enregistrer_retenue_garantie(
            self.co, date_constitution=date(2026, 1, 5), base=Decimal('1000'),
            user=self.user)
        services.liberer_retenue_garantie(
            rg, date_liberation=date(2027, 1, 5))
        rg.refresh_from_db()
        self.assertEqual(rg.statut, RetenueGarantie.Statut.LIBEREE)
        self.assertEqual(rg.date_liberation, date(2027, 1, 5))

    def test_liberer_date_defaut_aujourdhui(self):
        rg = services.enregistrer_retenue_garantie(
            self.co, date_constitution=date(2026, 1, 5), base=Decimal('1000'),
            user=self.user)
        services.liberer_retenue_garantie(rg)
        rg.refresh_from_db()
        self.assertEqual(rg.date_liberation, timezone.now().date())


# ── Caution bancaire : service & transitions ──────────────────────────────
class CautionBancaireServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg145-c-svc', 'FG145 Caution Svc')
        self.user = make_user(self.co, 'fg145-c-svc-user')

    def test_creation_pose_reference_et_statut_active(self):
        c = services.enregistrer_caution_bancaire(
            self.co,
            type_caution=CautionBancaire.TypeCaution.DEFINITIVE,
            date_emission=date(2026, 1, 10), montant=Decimal('50000'),
            banque='BMCE', marche_ref='MARCHE-X', user=self.user)
        self.assertTrue(c.reference.startswith('CAUTION-'))
        self.assertEqual(c.statut, CautionBancaire.Statut.ACTIVE)
        self.assertEqual(c.montant, Decimal('50000'))
        self.assertEqual(c.created_by, self.user)

    def test_type_defaut_definitive(self):
        c = services.enregistrer_caution_bancaire(
            self.co, date_emission=date(2026, 1, 10), montant=Decimal('100'),
            user=self.user)
        self.assertEqual(
            c.type_caution, CautionBancaire.TypeCaution.DEFINITIVE)

    def test_mainlevee_pose_statut_levee_et_date(self):
        c = services.enregistrer_caution_bancaire(
            self.co, date_emission=date(2026, 1, 10), montant=Decimal('100'),
            user=self.user)
        services.mainlevee_caution_bancaire(
            c, date_mainlevee=date(2026, 6, 1))
        c.refresh_from_db()
        self.assertEqual(c.statut, CautionBancaire.Statut.LEVEE)
        self.assertEqual(c.date_mainlevee, date(2026, 6, 1))

    def test_mainlevee_restituee(self):
        c = services.enregistrer_caution_bancaire(
            self.co,
            type_caution=CautionBancaire.TypeCaution.RESTITUTION,
            date_emission=date(2026, 1, 10), montant=Decimal('100'),
            user=self.user)
        services.mainlevee_caution_bancaire(c, restituee=True)
        c.refresh_from_db()
        self.assertEqual(c.statut, CautionBancaire.Statut.RESTITUEE)
        self.assertEqual(c.date_mainlevee, timezone.now().date())


# ── Sélecteurs d'échéances (maturité sous N jours) ────────────────────────
class EcheancesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('fg145-ech', 'FG145 Echeances')
        self.user = make_user(self.co, 'fg145-ech-user')
        self.today = date(2026, 6, 1)

    def _rg(self, levee, base='1000', statut=None):
        rg = services.enregistrer_retenue_garantie(
            self.co, date_constitution=date(2026, 1, 1), base=Decimal(base),
            date_levee_prevue=levee, user=self.user)
        if statut:
            rg.statut = statut
            rg.save(update_fields=['statut'])
        return rg

    def test_rg_dans_la_fenetre(self):
        # Levée dans 10 j → incluse ; levée dans 90 j → exclue à 30 j.
        self._rg(self.today + timedelta(days=10))
        self._rg(self.today + timedelta(days=90))
        data = selectors.retenues_garantie_a_echeance(
            self.co, jours=30, date_reference=self.today)
        self.assertEqual(data['nb'], 1)
        self.assertEqual(len(data['lignes']), 1)
        self.assertEqual(data['total_montant'], Decimal('100.00'))

    def test_rg_en_retard_incluse_et_signalee(self):
        # Levée déjà passée et non libérée → incluse, marquée en retard.
        self._rg(self.today - timedelta(days=5))
        data = selectors.retenues_garantie_a_echeance(
            self.co, jours=30, date_reference=self.today)
        self.assertEqual(data['nb'], 1)
        self.assertTrue(data['lignes'][0]['en_retard'])

    def test_rg_liberee_exclue(self):
        self._rg(self.today + timedelta(days=10),
                 statut=RetenueGarantie.Statut.LIBEREE)
        data = selectors.retenues_garantie_a_echeance(
            self.co, jours=30, date_reference=self.today)
        self.assertEqual(data['nb'], 0)

    def test_cautions_dans_la_fenetre(self):
        services.enregistrer_caution_bancaire(
            self.co, date_emission=date(2026, 1, 1), montant=Decimal('5000'),
            date_echeance=self.today + timedelta(days=15), user=self.user)
        c2 = services.enregistrer_caution_bancaire(
            self.co, date_emission=date(2026, 1, 1), montant=Decimal('999'),
            date_echeance=self.today + timedelta(days=15), user=self.user)
        # Une caution déjà levée ne ressort pas.
        services.mainlevee_caution_bancaire(c2)
        data = selectors.cautions_a_echeance(
            self.co, jours=30, date_reference=self.today)
        self.assertEqual(data['nb'], 1)
        self.assertEqual(data['total_montant'], Decimal('5000'))

    def test_cautions_hors_fenetre_exclue(self):
        services.enregistrer_caution_bancaire(
            self.co, date_emission=date(2026, 1, 1), montant=Decimal('5000'),
            date_echeance=self.today + timedelta(days=120), user=self.user)
        data = selectors.cautions_a_echeance(
            self.co, jours=30, date_reference=self.today)
        self.assertEqual(data['nb'], 0)


# ── API : isolation, pose serveur, actions, filtres, rôle ─────────────────
class RetenueGarantieApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg145-a', 'FG145 A')
        self.co_b = make_company('fg145-b', 'FG145 B')
        self.user_a = make_user(self.co_a, 'fg145-user-a')
        self.user_b = make_user(self.co_b, 'fg145-user-b')
        services.enregistrer_retenue_garantie(
            self.co_a, date_constitution=date(2026, 1, 10),
            base=Decimal('100000'), marche_ref='MA', user=self.user_a)

    def test_create_pose_company_et_montant_serveur(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/retenues-garantie/',
            {'date_constitution': '2026-02-01', 'base': '80000', 'taux': '5',
             'marche_ref': 'MB',
             'montant': '999999',          # tentative d'imposer le montant.
             'company': self.co_b.id},     # injection ignorée.
            format='json')
        self.assertEqual(resp.status_code, 201)
        # 80000 × 5 % = 4000, jamais 999999.
        self.assertEqual(Decimal(str(resp.data['montant'])), Decimal('4000.00'))
        rg = RetenueGarantie.objects.get(id=resp.data['id'])
        self.assertEqual(rg.company_id, self.co_a.id)

    def test_liste_isolee_par_societe(self):
        resp_b = auth(self.user_b).get(
            '/api/django/compta/retenues-garantie/')
        self.assertEqual(resp_b.status_code, 200)
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_action_liberer(self):
        rg = RetenueGarantie.objects.filter(company=self.co_a).first()
        resp = auth(self.user_a).post(
            f'/api/django/compta/retenues-garantie/{rg.id}/liberer/',
            {'date_liberation': '2027-01-10'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], RetenueGarantie.Statut.LIBEREE)
        self.assertEqual(resp.data['date_liberation'], '2027-01-10')

    def test_filtre_statut(self):
        rg = RetenueGarantie.objects.filter(company=self.co_a).first()
        services.liberer_retenue_garantie(rg)
        resp = auth(self.user_a).get(
            '/api/django/compta/retenues-garantie/',
            {'statut': RetenueGarantie.Statut.RETENUE})
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)

    def test_echeances_export_csv(self):
        services.enregistrer_retenue_garantie(
            self.co_a, date_constitution=date(2026, 1, 1),
            base=Decimal('1000'),
            date_levee_prevue=timezone.now().date() + timedelta(days=5),
            marche_ref='ME', user=self.user_a)
        resp = auth(self.user_a).get(
            '/api/django/compta/retenues-garantie/echeances/',
            {'jours': '30', 'export': 'csv'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('Retenues de garantie', resp.content.decode('utf-8'))

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg145-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/retenues-garantie/',
            {'date_constitution': '2026-01-01', 'base': '1000'},
            format='json')
        self.assertEqual(resp.status_code, 403)


class CautionBancaireApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg145-ca', 'FG145 CA')
        self.co_b = make_company('fg145-cb', 'FG145 CB')
        self.user_a = make_user(self.co_a, 'fg145-ca-user')
        self.user_b = make_user(self.co_b, 'fg145-cb-user')

    def test_create_pose_company_serveur(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/cautions-bancaires/',
            {'type_caution': 'provisoire', 'date_emission': '2026-01-10',
             'montant': '50000', 'banque': 'CIH', 'marche_ref': 'MX',
             'company': self.co_b.id},   # injection ignorée.
            format='json')
        self.assertEqual(resp.status_code, 201)
        c = CautionBancaire.objects.get(id=resp.data['id'])
        self.assertEqual(c.company_id, self.co_a.id)
        self.assertEqual(c.statut, CautionBancaire.Statut.ACTIVE)
        self.assertTrue(c.reference.startswith('CAUTION-'))

    def test_action_mainlevee_restituee(self):
        c = services.enregistrer_caution_bancaire(
            self.co_a, date_emission=date(2026, 1, 10), montant=Decimal('100'),
            user=self.user_a)
        resp = auth(self.user_a).post(
            f'/api/django/compta/cautions-bancaires/{c.id}/mainlevee/',
            {'restituee': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], CautionBancaire.Statut.RESTITUEE)
        self.assertTrue(resp.data['date_mainlevee'])

    def test_filtre_type_caution(self):
        services.enregistrer_caution_bancaire(
            self.co_a, type_caution=CautionBancaire.TypeCaution.PROVISOIRE,
            date_emission=date(2026, 1, 10), montant=Decimal('100'),
            user=self.user_a)
        services.enregistrer_caution_bancaire(
            self.co_a, type_caution=CautionBancaire.TypeCaution.DEFINITIVE,
            date_emission=date(2026, 1, 11), montant=Decimal('200'),
            user=self.user_a)
        resp = auth(self.user_a).get(
            '/api/django/compta/cautions-bancaires/',
            {'type_caution': 'provisoire'})
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['type_caution'], 'provisoire')

    def test_isolation_liste(self):
        services.enregistrer_caution_bancaire(
            self.co_a, date_emission=date(2026, 1, 10), montant=Decimal('100'),
            user=self.user_a)
        resp_b = auth(self.user_b).get(
            '/api/django/compta/cautions-bancaires/')
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg145-ca-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/cautions-bancaires/',
            {'date_emission': '2026-01-01', 'montant': '100'},
            format='json')
        self.assertEqual(resp.status_code, 403)
