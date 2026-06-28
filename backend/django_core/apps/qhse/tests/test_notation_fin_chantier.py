"""Tests QHSE17 — Grille de notation fin de chantier + gate clôture.

Couvre :
* création d'une ``NotationFinChantier`` : company forcée, auteur forcé côté
  serveur ;
* création d'un ``ItemNotation`` : company forcée, notation d'une autre société
  refusée ;
* ``calculer_score_notation`` : score pondéré, verdict passe/échec, cas sans item,
  items non renseignés exclus du calcul ;
* sélecteur ``chantier_peut_cloturer`` : True si aucune notation, True si verdict
  PASSE, False si verdict ECHEC, non-bloquant sur verdict None ;
* endpoints API CRUD + ``calculer`` + ``peut-cloturer`` ;
* isolation entre sociétés.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ItemNotation, NotationFinChantier
from apps.qhse.selectors import chantier_peut_cloturer
from apps.qhse.services import calculer_score_notation

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_notation(company, chantier_id=1, auteur=None, seuil=70):
    return NotationFinChantier.objects.create(
        company=company,
        chantier_id=chantier_id,
        auteur=auteur,
        seuil_passage=seuil,
    )


def make_item(company, notation, intitule='Item', poids=1, conforme=None):
    return ItemNotation.objects.create(
        company=company,
        notation=notation,
        intitule=intitule,
        poids=poids,
        conforme=conforme,
    )


# ── Tests service ``calculer_score_notation`` ─────────────────────────────────

class CalculerScoreNotationTests(TestCase):
    """Tests du service de calcul de score de notation fin de chantier."""

    def setUp(self):
        self.co = make_company('qhse17-score', 'Score17')

    def test_score_tous_conformes(self):
        """Score = 100 % quand tous les items sont conformes."""
        notation = make_notation(self.co)
        make_item(self.co, notation, 'A', poids=3, conforme=True)
        make_item(self.co, notation, 'B', poids=2, conforme=True)
        calculer_score_notation(notation)
        notation.refresh_from_db()
        self.assertEqual(notation.score, Decimal('100.00'))
        self.assertEqual(notation.verdict, NotationFinChantier.Verdict.PASSE)

    def test_score_partiel_passe(self):
        """Score = 60 % (poids 3 conforme sur 3+2) — passe au seuil 70 ? Non."""
        notation = make_notation(self.co, seuil=70)
        make_item(self.co, notation, 'A', poids=3, conforme=True)
        make_item(self.co, notation, 'B', poids=2, conforme=False)
        calculer_score_notation(notation)
        notation.refresh_from_db()
        self.assertEqual(notation.score, Decimal('60.00'))
        self.assertEqual(notation.verdict, NotationFinChantier.Verdict.ECHEC)

    def test_score_partiel_avec_seuil_bas_passe(self):
        """Score = 60 % avec seuil 50 → PASSE."""
        notation = make_notation(self.co, seuil=50)
        make_item(self.co, notation, 'A', poids=3, conforme=True)
        make_item(self.co, notation, 'B', poids=2, conforme=False)
        calculer_score_notation(notation)
        notation.refresh_from_db()
        self.assertEqual(notation.score, Decimal('60.00'))
        self.assertEqual(notation.verdict, NotationFinChantier.Verdict.PASSE)

    def test_score_zero_echec(self):
        """Score = 0 % → ECHEC."""
        notation = make_notation(self.co)
        make_item(self.co, notation, 'A', poids=1, conforme=False)
        make_item(self.co, notation, 'B', poids=1, conforme=False)
        calculer_score_notation(notation)
        notation.refresh_from_db()
        self.assertEqual(notation.score, Decimal('0.00'))
        self.assertEqual(notation.verdict, NotationFinChantier.Verdict.ECHEC)

    def test_score_none_si_aucun_item_renseigne(self):
        """Aucun item non-nul → score None, verdict None."""
        notation = make_notation(self.co)
        make_item(self.co, notation, 'A', poids=2, conforme=None)
        calculer_score_notation(notation)
        notation.refresh_from_db()
        self.assertIsNone(notation.score)
        self.assertIsNone(notation.verdict)

    def test_items_non_renseignes_exclus_du_calcul(self):
        """Items conforme=None exclus du calcul ; seuls les renseignés comptent."""
        notation = make_notation(self.co, seuil=70)
        make_item(self.co, notation, 'A', poids=4, conforme=True)
        make_item(self.co, notation, 'B', poids=1, conforme=False)
        make_item(self.co, notation, 'C', poids=10, conforme=None)  # exclu
        # score = 4/(4+1)*100 = 80.00 → PASSE
        calculer_score_notation(notation)
        notation.refresh_from_db()
        self.assertEqual(notation.score, Decimal('80.00'))
        self.assertEqual(notation.verdict, NotationFinChantier.Verdict.PASSE)

    def test_score_exactement_au_seuil_passe(self):
        """Score == seuil_passage → PASSE (borne inclusive)."""
        notation = make_notation(self.co, seuil=70)
        make_item(self.co, notation, 'A', poids=7, conforme=True)
        make_item(self.co, notation, 'B', poids=3, conforme=False)
        # score = 70.00 == seuil 70 → PASSE
        calculer_score_notation(notation)
        notation.refresh_from_db()
        self.assertEqual(notation.score, Decimal('70.00'))
        self.assertEqual(notation.verdict, NotationFinChantier.Verdict.PASSE)


# ── Tests sélecteur ``chantier_peut_cloturer`` ────────────────────────────────

class ChantierPeutCloturerTests(TestCase):
    """Tests du sélecteur advisory de clôture."""

    def setUp(self):
        self.co = make_company('qhse17-gate', 'Gate17')

    def test_aucune_notation_peut_cloturer(self):
        """Pas de notation → True (advisory : pas de blocage par défaut)."""
        self.assertTrue(chantier_peut_cloturer(99, self.co))

    def test_verdict_passe_peut_cloturer(self):
        notation = make_notation(self.co, chantier_id=10)
        notation.verdict = NotationFinChantier.Verdict.PASSE
        notation.score = Decimal('80.00')
        notation.save(update_fields=['verdict', 'score'])
        self.assertTrue(chantier_peut_cloturer(10, self.co))

    def test_verdict_echec_ne_peut_pas_cloturer(self):
        notation = make_notation(self.co, chantier_id=11)
        notation.verdict = NotationFinChantier.Verdict.ECHEC
        notation.score = Decimal('50.00')
        notation.save(update_fields=['verdict', 'score'])
        self.assertFalse(chantier_peut_cloturer(11, self.co))

    def test_verdict_none_peut_cloturer(self):
        """Verdict non encore calculé (None) → pas de blocage."""
        make_notation(self.co, chantier_id=12)  # verdict=None par défaut
        self.assertTrue(chantier_peut_cloturer(12, self.co))

    def test_isolation_societes_gate(self):
        """La notation d'une autre société n'affecte pas la gate."""
        other = make_company('qhse17-gate-b', 'GateB')
        notation = make_notation(other, chantier_id=20)
        notation.verdict = NotationFinChantier.Verdict.ECHEC
        notation.score = Decimal('0.00')
        notation.save(update_fields=['verdict', 'score'])
        # Pour self.co, ce chantier n'a pas de notation → True
        self.assertTrue(chantier_peut_cloturer(20, self.co))

    def test_plus_recente_notation_prise_en_compte(self):
        """La notation la plus récente (id le plus élevé) fait foi."""
        notation_old = make_notation(self.co, chantier_id=30)
        notation_old.verdict = NotationFinChantier.Verdict.ECHEC
        notation_old.score = Decimal('40.00')
        notation_old.save(update_fields=['verdict', 'score'])
        # Notation plus récente : PASSE
        notation_new = make_notation(self.co, chantier_id=30)
        notation_new.verdict = NotationFinChantier.Verdict.PASSE
        notation_new.score = Decimal('90.00')
        notation_new.save(update_fields=['verdict', 'score'])
        self.assertTrue(chantier_peut_cloturer(30, self.co))


# ── Tests API ─────────────────────────────────────────────────────────────────

class NotationFinChantierApiTests(TestCase):
    NOTATIONS = '/api/django/qhse/notations-fin-chantier/'
    ITEMS = '/api/django/qhse/items-notation/'

    def setUp(self):
        self.co = make_company('qhse17-api', 'Api17')
        self.user = make_user(self.co, 'qhse17-api')
        self.client = auth_client(self.user)

    # --- Notation CRUD -------------------------------------------------------

    def test_create_notation_forces_company_and_auteur(self):
        resp = self.client.post(
            self.NOTATIONS,
            {'chantier_id': 1, 'date_notation': '2026-06-28'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        notation = NotationFinChantier.objects.get(id=resp.data['id'])
        self.assertEqual(notation.company, self.co)
        self.assertEqual(notation.auteur, self.user)

    def test_list_notation_scoped_to_company(self):
        other = make_company('qhse17-api-b', 'B17')
        make_notation(other, chantier_id=5)
        make_notation(self.co, chantier_id=5)
        resp = self.client.get(self.NOTATIONS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_filter_by_chantier_id(self):
        make_notation(self.co, chantier_id=1)
        make_notation(self.co, chantier_id=2)
        resp = self.client.get(f'{self.NOTATIONS}?chantier_id=1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_calculer_action(self):
        """POST /notations-fin-chantier/<id>/calculer/ calcule score + verdict."""
        notation = make_notation(self.co, chantier_id=7)
        make_item(self.co, notation, 'Sécurité', poids=3, conforme=True)
        make_item(self.co, notation, 'Qualité câblage', poids=2, conforme=False)
        resp = self.client.post(f'{self.NOTATIONS}{notation.id}/calculer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        # score = 3/(3+2)*100 = 60.00 < 70 → echec
        self.assertEqual(resp.data['score'], '60.00')
        self.assertEqual(resp.data['verdict'], 'echec')

    def test_peut_cloturer_action_sans_notation(self):
        """GET /notations-fin-chantier/peut-cloturer/?chantier_id= → True si aucune."""
        resp = self.client.get(f'{self.NOTATIONS}peut-cloturer/?chantier_id=99')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['peut_cloturer'])

    def test_peut_cloturer_action_echec(self):
        notation = make_notation(self.co, chantier_id=50)
        notation.verdict = NotationFinChantier.Verdict.ECHEC
        notation.score = Decimal('30.00')
        notation.save(update_fields=['verdict', 'score'])
        resp = self.client.get(f'{self.NOTATIONS}peut-cloturer/?chantier_id=50')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['peut_cloturer'])

    def test_peut_cloturer_chantier_id_requis(self):
        resp = self.client.get(f'{self.NOTATIONS}peut-cloturer/')
        self.assertEqual(resp.status_code, 400)

    def test_peut_cloturer_chantier_id_invalide(self):
        resp = self.client.get(f'{self.NOTATIONS}peut-cloturer/?chantier_id=abc')
        self.assertEqual(resp.status_code, 400)

    # --- ItemNotation CRUD ---------------------------------------------------

    def test_create_item_forces_company(self):
        notation = make_notation(self.co, chantier_id=8)
        resp = self.client.post(
            self.ITEMS,
            {'notation': notation.id, 'intitule': 'Nettoyage', 'poids': 2,
             'conforme': True},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        item = ItemNotation.objects.get(id=resp.data['id'])
        self.assertEqual(item.company, self.co)

    def test_create_item_other_company_notation_refused(self):
        other = make_company('qhse17-api-c', 'C17')
        other_notation = make_notation(other, chantier_id=9)
        resp = self.client.post(
            self.ITEMS,
            {'notation': other_notation.id, 'intitule': 'Test', 'poids': 1,
             'conforme': True},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filter_items_by_notation(self):
        n1 = make_notation(self.co, chantier_id=10)
        n2 = make_notation(self.co, chantier_id=11)
        make_item(self.co, n1, 'I1', poids=1, conforme=True)
        make_item(self.co, n2, 'I2', poids=1, conforme=False)
        resp = self.client.get(f'{self.ITEMS}?notation={n1.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse17-normal', role='normal')
        resp = auth_client(normal).get(self.NOTATIONS)
        self.assertEqual(resp.status_code, 403)
