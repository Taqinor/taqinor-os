"""Tests FG176 — Garde d'affectation par habilitation (blocage doux).

Couvre la garde RH réutilisable que l'affectation (côté installations) appelle
pour décider d'alerter/bloquer :

* Selector ``verifier_habilitation_requise`` : autorisé quand chaque titre requis
  est valide ; non autorisé quand un titre manque (jamais obtenu) ou est expiré/
  inactif ; remplissage des listes ``manquantes`` vs ``expirees`` ; titre unique
  ou liste de titres ; entrées vides ignorées ; société/employé manquant → non
  autorisé ; ``today`` injectable.
* Carte ``INTERVENTION_HABILITATIONS`` via
  ``habilitations_requises_pour_intervention``.
* Cadrage société : un titre d'une AUTRE société ne valide jamais l'employé.
* Endpoint ``GET employes/{id}/verifier-habilitation/?type=&intervention=`` :
  rapport correct, scopé société (employé d'une autre société → 404), 403 sans
  rôle.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, Habilitation

User = get_user_model()

EMP = '/api/django/rh/employes/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_habilitation(company, employe, type_habilitation='b1v',
                      date_validite=None, actif=True):
    return Habilitation.objects.create(
        company=company, employe=employe,
        type_habilitation=type_habilitation,
        date_validite=date_validite, actif=actif)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VerifierHabilitationSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gardeh-a', 'A')
        self.co_b = make_company('gardeh-b', 'B')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.today = timezone.localdate()

    def test_autorise_quand_titre_valide(self):
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=30))
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, 'b1v')
        self.assertTrue(res['autorise'])
        self.assertEqual(res['manquantes'], [])
        self.assertEqual(res['expirees'], [])

    def test_autorise_titre_sans_echeance(self):
        make_habilitation(self.co_a, self.emp_a, 'b0', date_validite=None)
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, 'b0')
        self.assertTrue(res['autorise'])

    def test_non_autorise_titre_manquant(self):
        # Aucune ligne pour ce titre → manquante.
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, 'br')
        self.assertFalse(res['autorise'])
        self.assertEqual(res['manquantes'], ['br'])
        self.assertEqual(res['expirees'], [])

    def test_non_autorise_titre_expire(self):
        # Le titre EXISTE mais l'échéance est dépassée → expiree, pas manquante.
        make_habilitation(
            self.co_a, self.emp_a, 'b2v',
            date_validite=self.today - timedelta(days=1))
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, 'b2v')
        self.assertFalse(res['autorise'])
        self.assertEqual(res['expirees'], ['b2v'])
        self.assertEqual(res['manquantes'], [])

    def test_non_autorise_titre_inactif_compte_comme_expire(self):
        make_habilitation(
            self.co_a, self.emp_a, 'br',
            date_validite=self.today + timedelta(days=365), actif=False)
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, 'br')
        self.assertFalse(res['autorise'])
        self.assertEqual(res['expirees'], ['br'])

    def test_liste_titres_manquantes_et_expirees(self):
        # b1v valide, br expiré, bc jamais obtenu.
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=10))
        make_habilitation(
            self.co_a, self.emp_a, 'br',
            date_validite=self.today - timedelta(days=2))
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, ['b1v', 'br', 'bc'])
        self.assertFalse(res['autorise'])
        self.assertEqual(res['manquantes'], ['bc'])
        self.assertEqual(res['expirees'], ['br'])

    def test_accepte_id_employe(self):
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=10))
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a.pk, 'b1v')
        self.assertTrue(res['autorise'])

    def test_entrees_vides_ignorees(self):
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=10))
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, ['', 'b1v', None])
        self.assertTrue(res['autorise'])

    def test_aucun_titre_requis_non_autorise(self):
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, [])
        self.assertFalse(res['autorise'])
        self.assertIn('Aucune habilitation', res['message'])

    def test_societe_manquante_non_autorise(self):
        res = selectors.verifier_habilitation_requise(
            None, self.emp_a, 'b1v')
        self.assertFalse(res['autorise'])

    def test_employe_manquant_non_autorise(self):
        res = selectors.verifier_habilitation_requise(
            self.co_a, None, 'b1v')
        self.assertFalse(res['autorise'])

    def test_today_injectable(self):
        # Échéance demain : expirée si l'on évalue à +2 jours.
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=1))
        futur = self.today + timedelta(days=2)
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, 'b1v', today=futur)
        self.assertFalse(res['autorise'])
        self.assertEqual(res['expirees'], ['b1v'])

    def test_cadrage_societe_titre_autre_societe_ne_valide_pas(self):
        # emp_a n'a pas le titre ; un titre du MÊME code existe chez B mais ne
        # doit jamais autoriser l'employé A.
        make_habilitation(
            self.co_b, self.emp_b, 'b1v',
            date_validite=self.today + timedelta(days=365))
        res = selectors.verifier_habilitation_requise(
            self.co_a, self.emp_a, 'b1v')
        self.assertFalse(res['autorise'])
        self.assertEqual(res['manquantes'], ['b1v'])


class HabilitationsRequisesInterventionTests(TestCase):
    def test_type_connu_renvoie_titres(self):
        titres = selectors.habilitations_requises_pour_intervention('pose_pv_bt')
        self.assertEqual(titres, ['b1v', 'br'])

    def test_type_inconnu_renvoie_liste_vide(self):
        self.assertEqual(
            selectors.habilitations_requises_pour_intervention('inconnu'), [])

    def test_type_vide_renvoie_liste_vide(self):
        self.assertEqual(
            selectors.habilitations_requises_pour_intervention(''), [])

    def test_copie_defensive(self):
        # Muter le retour ne doit pas altérer la carte interne.
        titres = selectors.habilitations_requises_pour_intervention('pose_pv_bt')
        titres.append('hack')
        self.assertEqual(
            selectors.habilitations_requises_pour_intervention('pose_pv_bt'),
            ['b1v', 'br'])


class VerifierHabilitationEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gardee-a', 'A')
        self.co_b = make_company('gardee-b', 'B')
        self.user_a = make_user(self.co_a, 'gardee-user-a')
        self.user_b = make_user(self.co_b, 'gardee-user-b')
        self.normal = make_user(self.co_a, 'gardee-normal', role='employe')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.today = timezone.localdate()

    def _url(self, emp):
        return f'{EMP}{emp.pk}/verifier-habilitation/'

    def test_endpoint_autorise(self):
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=30))
        resp = auth(self.user_a).get(self._url(self.emp_a) + '?type=b1v')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['autorise'])
        self.assertEqual(resp.data['employe'], self.emp_a.pk)

    def test_endpoint_non_autorise_manquante(self):
        resp = auth(self.user_a).get(self._url(self.emp_a) + '?type=br')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['autorise'])
        self.assertEqual(resp.data['manquantes'], ['br'])

    def test_endpoint_types_multiples_repetes(self):
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=30))
        resp = auth(self.user_a).get(
            self._url(self.emp_a) + '?type=b1v&type=br')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['autorise'])
        self.assertEqual(resp.data['manquantes'], ['br'])

    def test_endpoint_types_separes_virgule(self):
        make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=self.today + timedelta(days=30))
        resp = auth(self.user_a).get(
            self._url(self.emp_a) + '?type=b1v,br')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['manquantes'], ['br'])

    def test_endpoint_intervention_traduit_titres(self):
        # pose_pv_bt exige b1v + br ; l'employé n'a aucun → les deux manquants.
        resp = auth(self.user_a).get(
            self._url(self.emp_a) + '?intervention=pose_pv_bt')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['autorise'])
        self.assertEqual(sorted(resp.data['manquantes']), ['b1v', 'br'])

    def test_endpoint_scope_societe_404(self):
        # user_a ne peut pas viser un employé de la société B.
        resp = auth(self.user_a).get(self._url(self.emp_b) + '?type=b1v')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_normal_refuse(self):
        resp = auth(self.normal).get(self._url(self.emp_a) + '?type=b1v')
        self.assertEqual(resp.status_code, 403)
