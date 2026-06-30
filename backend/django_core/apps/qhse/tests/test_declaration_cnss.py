"""Tests QHSE30 — Déclaration CNSS de l'accident du travail (échéance légale).

Couvre le modèle ``DeclarationCnss`` (calcul d'échéance + ``statut_calcule``),
le sélecteur ``declarations_cnss_a_echeance`` et le viewset
``/api/django/qhse/declarations-cnss/`` :

* la ``date_limite`` est calculée côté serveur (= ``date_accident`` +
  ``delai_jours``) ;
* transitions de statut : à déclarer / déclaré / hors délai ;
* fenêtre « à échéance » (approchantes + déjà hors délai), exclut les déclarées ;
* isolation entre sociétés (jamais les déclarations / accidents d'une autre) ;
* gating de rôle (un rôle normal est refusé).

L'accident du travail vit dans ``rh`` (FG181) ; QHSE30 ne le référence que par
FK-chaîne — ce test importe ``rh.AccidentTravail`` UNIQUEMENT pour fabriquer la
donnée d'amont, jamais le code QHSE.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import DeclarationCnss
from apps.qhse.selectors import declarations_cnss_a_echeance
from apps.rh.models import AccidentTravail, DossierEmploye

User = get_user_model()

LIST_URL = '/api/django/qhse/declarations-cnss/'
ECHEANCE_URL = '/api/django/qhse/declarations-cnss/a-echeance/'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


def make_accident(company, reference, jour):
    employe = DossierEmploye.objects.create(
        company=company, matricule=f'M-{reference}', nom='Test', prenom='X')
    return AccidentTravail.objects.create(
        company=company, employe=employe, reference=reference,
        date_accident=jour)


def make_declaration(company, accident, date_accident,
                     delai_jours=2, date_declaration=None):
    return DeclarationCnss.objects.create(
        company=company, accident_travail=accident,
        date_accident=date_accident, delai_jours=delai_jours,
        date_declaration=date_declaration)


# ── Modèle : calcul d'échéance + statut ────────────────────────────────────────

class DeclarationCnssModelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-cnss', 'CoCnss')
        self.today = timezone.localdate()

    def test_date_limite_calculee(self):
        jour = date(2026, 6, 10)
        acc = make_accident(self.company, 'AT-202606-0001', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=2)
        self.assertEqual(decl.date_limite, jour + timedelta(days=2))

    def test_delai_jours_parametrable(self):
        jour = date(2026, 6, 10)
        acc = make_accident(self.company, 'AT-202606-0002', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=5)
        self.assertEqual(decl.date_limite, jour + timedelta(days=5))

    def test_statut_a_declarer_dans_le_delai(self):
        acc = make_accident(self.company, 'AT-202606-0003', self.today)
        decl = make_declaration(self.company, acc, self.today, delai_jours=2)
        self.assertEqual(decl.statut, DeclarationCnss.Statut.A_DECLARER)
        self.assertEqual(
            decl.statut_calcule(self.today), DeclarationCnss.Statut.A_DECLARER)

    def test_statut_hors_delai_si_echeance_passee(self):
        jour = self.today - timedelta(days=10)
        acc = make_accident(self.company, 'AT-202606-0004', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=2)
        self.assertEqual(decl.statut, DeclarationCnss.Statut.HORS_DELAI)

    def test_statut_declare_fige_meme_hors_delai(self):
        # Accident ancien (échéance dépassée) MAIS déclaration enregistrée :
        # l'état est figé sur « déclaré », jamais « hors délai ».
        jour = self.today - timedelta(days=30)
        acc = make_accident(self.company, 'AT-202606-0005', jour)
        decl = make_declaration(
            self.company, acc, jour, delai_jours=2,
            date_declaration=self.today)
        self.assertEqual(decl.statut, DeclarationCnss.Statut.DECLARE)
        self.assertEqual(
            decl.statut_calcule(self.today), DeclarationCnss.Statut.DECLARE)

    def test_statut_rafraichi_a_la_declaration(self):
        jour = self.today - timedelta(days=10)
        acc = make_accident(self.company, 'AT-202606-0006', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=2)
        self.assertEqual(decl.statut, DeclarationCnss.Statut.HORS_DELAI)
        # On enregistre la déclaration → l'état bascule sur « déclaré ».
        decl.date_declaration = self.today
        decl.numero_declaration = 'CNSS-2026-42'
        decl.save()
        decl.refresh_from_db()
        self.assertEqual(decl.statut, DeclarationCnss.Statut.DECLARE)


# ── Sélecteur : déclarations à échéance ────────────────────────────────────────

class DeclarationCnssEcheanceSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('co-cnss-sel', 'CoCnssSel')
        self.other = make_company('co-cnss-sel-2', 'CoCnssSel2')
        self.today = timezone.localdate()

    def test_dans_la_fenetre_signale(self):
        jour = self.today  # limite = today + 2
        acc = make_accident(self.company, 'AT-202606-0001', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=2)
        ids = list(declarations_cnss_a_echeance(
            self.company, within_days=2).values_list('id', flat=True))
        self.assertIn(decl.id, ids)

    def test_hors_fenetre_exclu(self):
        jour = self.today + timedelta(days=30)  # limite loin dans le futur
        acc = make_accident(self.company, 'AT-202606-0002', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=2)
        ids = list(declarations_cnss_a_echeance(
            self.company, within_days=2).values_list('id', flat=True))
        self.assertNotIn(decl.id, ids)

    def test_hors_delai_inclus(self):
        jour = self.today - timedelta(days=10)
        acc = make_accident(self.company, 'AT-202606-0003', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=2)
        ids = list(declarations_cnss_a_echeance(
            self.company, within_days=2).values_list('id', flat=True))
        self.assertIn(decl.id, ids)

    def test_declaree_exclue(self):
        jour = self.today - timedelta(days=10)
        acc = make_accident(self.company, 'AT-202606-0004', jour)
        decl = make_declaration(
            self.company, acc, jour, delai_jours=2,
            date_declaration=self.today)
        ids = list(declarations_cnss_a_echeance(
            self.company, within_days=2).values_list('id', flat=True))
        self.assertNotIn(decl.id, ids)

    def test_isolation_societe(self):
        jour = self.today - timedelta(days=5)
        acc = make_accident(self.other, 'AT-202606-0001', jour)
        autre = make_declaration(self.other, acc, jour, delai_jours=2)
        ids = list(declarations_cnss_a_echeance(
            self.company, within_days=2).values_list('id', flat=True))
        self.assertNotIn(autre.id, ids)

    def test_tri_echeance_la_plus_proche_dabord(self):
        loin_jour = self.today + timedelta(days=1)  # limite = +3
        proche_jour = self.today - timedelta(days=1)  # limite = +1
        acc_loin = make_accident(self.company, 'AT-202606-0007', loin_jour)
        acc_proche = make_accident(self.company, 'AT-202606-0008', proche_jour)
        loin = make_declaration(self.company, acc_loin, loin_jour, delai_jours=2)
        proche = make_declaration(
            self.company, acc_proche, proche_jour, delai_jours=2)
        ids = list(declarations_cnss_a_echeance(
            self.company, within_days=5).values_list('id', flat=True))
        self.assertEqual(ids, [proche.id, loin.id])

    def test_societe_absente_renvoie_vide(self):
        self.assertEqual(list(declarations_cnss_a_echeance(None)), [])


# ── API : viewset + action a-echeance + gating ────────────────────────────────

class DeclarationCnssApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-cnss-api', 'CoCnssApi')
        self.other = make_company('co-cnss-api-2', 'CoCnssApi2')
        self.user = make_user(self.company, 'cnss-resp')
        self.client_api = auth_client(self.user)
        self.today = timezone.localdate()

    def test_create_pose_company_et_calcule_echeance(self):
        jour = self.today
        acc = make_accident(self.company, 'AT-202606-0010', jour)
        resp = self.client_api.post(LIST_URL, {
            'accident_travail': acc.id,
            'date_accident': jour.isoformat(),
            'delai_jours': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        decl = DeclarationCnss.objects.get(id=resp.data['id'])
        self.assertEqual(decl.company_id, self.company.id)
        self.assertEqual(decl.date_limite, jour + timedelta(days=2))
        self.assertEqual(decl.statut, DeclarationCnss.Statut.A_DECLARER)

    def test_create_refuse_accident_autre_societe(self):
        jour = self.today
        acc_autre = make_accident(self.other, 'AT-202606-0011', jour)
        resp = self.client_api.post(LIST_URL, {
            'accident_travail': acc_autre.id,
            'date_accident': jour.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_a_echeance_liste(self):
        jour_dedans = self.today
        acc1 = make_accident(self.company, 'AT-202606-0012', jour_dedans)
        dedans = make_declaration(
            self.company, acc1, jour_dedans, delai_jours=2)
        jour_loin = self.today + timedelta(days=60)
        acc2 = make_accident(self.company, 'AT-202606-0013', jour_loin)
        make_declaration(self.company, acc2, jour_loin, delai_jours=2)
        resp = self.client_api.get(ECHEANCE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(ids, {dedans.id})

    def test_a_echeance_within_days_param(self):
        jour = self.today + timedelta(days=8)  # limite = +10
        acc = make_accident(self.company, 'AT-202606-0014', jour)
        decl = make_declaration(self.company, acc, jour, delai_jours=2)
        # Fenêtre par défaut (2 j) : exclu ; fenêtre large : inclus.
        resp_defaut = self.client_api.get(ECHEANCE_URL)
        self.assertNotIn(
            decl.id, {r['id'] for r in rows(resp_defaut)})
        resp_large = self.client_api.get(ECHEANCE_URL, {'within_days': '15'})
        self.assertIn(decl.id, {r['id'] for r in rows(resp_large)})

    def test_a_echeance_isolation_societe(self):
        jour = self.today
        acc = make_accident(self.other, 'AT-202606-0015', jour)
        make_declaration(self.other, acc, jour, delai_jours=2)
        resp = self.client_api.get(ECHEANCE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(rows(resp), [])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'cnss-normal', role='normal')
        resp = auth_client(normal).get(ECHEANCE_URL)
        self.assertEqual(resp.status_code, 403)
