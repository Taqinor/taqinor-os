"""Tests WIR172 — permissions fines ``rh_voir`` / ``rh_gerer``.

Le module RH (66 ViewSets sur ``_RhBaseViewSet`` : dossiers employés,
sanctions disciplinaires, visites médicales…) n'était gardé que par le
grossier ``IsResponsableOrAdmin``. Or ``is_responsable`` est vrai dès qu'un
rôle porte UNE permission d'écriture, MÊME hors RH : un Commercial
(``crm_creer``) obtenait le CRUD complet des dossiers employés.

Couvre :
* les deux codes existent au catalogue et le rôle système « Responsable » les
  porte (accès historique préservé) ;
* un rôle « Commercial » (écritures CRM/Ventes, aucun code RH) → 403 sur
  dossiers, sanctions et visites médicales, en lecture ET en écriture ;
* ``rh_voir`` SEUL = lecture autorisée / écriture refusée ;
* ``rh_voir`` + ``rh_gerer`` = lecture et écriture autorisées ;
* légacy INCHANGÉ : un compte sans rôle fin garde son comportement
  (``responsable`` passe, ``normal`` reste refusé) ;
* les trois exceptions de lecture élargie sont préservées : ``annuaire`` et
  ``localisation-du-jour`` (tout interne authentifié) et ``compa-ratio``
  (``salaires_voir`` seul, même sans aucun droit RH).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye
from apps.roles.models import (
    ALL_PERMISSIONS,
    COMMERCIAL_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
    Role,
)

User = get_user_model()

URL_EMPLOYES = '/api/django/rh/employes/'
URL_SANCTIONS = '/api/django/rh/sanctions/'
URL_VISITES = '/api/django/rh/visites-medicales/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CatalogueWir172Tests(TestCase):
    def test_les_deux_codes_sont_au_catalogue(self):
        self.assertIn('rh_voir', ALL_PERMISSIONS)
        self.assertIn('rh_gerer', ALL_PERMISSIONS)

    def test_responsable_garde_son_acces_historique(self):
        self.assertIn('rh_voir', RESPONSABLE_PERMISSIONS)
        self.assertIn('rh_gerer', RESPONSABLE_PERMISSIONS)

    def test_commercial_ne_porte_aucun_code_rh(self):
        """Le resserrement est le but même de la tâche."""
        self.assertNotIn('rh_voir', COMMERCIAL_PERMISSIONS)
        self.assertNotIn('rh_gerer', COMMERCIAL_PERMISSIONS)


class GardeRhParRoleTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='WIR172 Co', slug='wir172-co')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='W1', nom='Nom', prenom='Prenom')

    def _user(self, username, permissions):
        role = Role.objects.create(
            company=self.co, nom=f'role-{username}',
            permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.co, role=role)

    def _legacy(self, username, role_legacy):
        return User.objects.create_user(
            username=username, password='x', company=self.co,
            role_legacy=role_legacy)

    def _payload_employe(self, matricule):
        return {'matricule': matricule, 'nom': 'X', 'prenom': 'Y'}

    # ── Le bug corrigé ────────────────────────────────────────────────────
    def test_commercial_403_sur_dossiers_sanctions_visites(self):
        commercial = self._user('wir172-commercial', COMMERCIAL_PERMISSIONS)
        api = auth(commercial)
        for url in (URL_EMPLOYES, URL_SANCTIONS, URL_VISITES):
            self.assertEqual(api.get(url).status_code, 403, url)
        resp = api.post(URL_EMPLOYES, self._payload_employe('W2'))
        self.assertEqual(resp.status_code, 403)

    def test_ecriture_hors_rh_ne_donne_plus_le_crud_rh(self):
        """Le cœur du bug : UNE écriture hors RH suffisait à passer."""
        porteur = self._user('wir172-crm-only', ['crm_voir', 'crm_creer'])
        self.assertEqual(auth(porteur).get(URL_EMPLOYES).status_code, 403)

    # ── Lecture / écriture séparées ───────────────────────────────────────
    def test_rh_voir_seul_lit_mais_n_ecrit_pas(self):
        lecteur = self._user('wir172-lecteur', ['rh_voir'])
        api = auth(lecteur)
        self.assertEqual(api.get(URL_EMPLOYES).status_code, 200)
        self.assertEqual(api.get(URL_SANCTIONS).status_code, 200)
        self.assertEqual(api.get(URL_VISITES).status_code, 200)
        resp = api.post(URL_EMPLOYES, self._payload_employe('W3'))
        self.assertEqual(resp.status_code, 403)

    def test_rh_gerer_ecrit(self):
        gestionnaire = self._user('wir172-gest', ['rh_voir', 'rh_gerer'])
        api = auth(gestionnaire)
        self.assertEqual(api.get(URL_EMPLOYES).status_code, 200)
        resp = api.post(URL_EMPLOYES, self._payload_employe('W4'))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['matricule'], 'W4')

    # ── Légacy strictement inchangé ───────────────────────────────────────
    def test_legacy_responsable_inchange(self):
        legacy = self._legacy('wir172-legacy-resp', 'responsable')
        api = auth(legacy)
        self.assertEqual(api.get(URL_EMPLOYES).status_code, 200)
        resp = api.post(URL_EMPLOYES, self._payload_employe('W5'))
        self.assertEqual(resp.status_code, 201)

    def test_legacy_normal_toujours_refuse(self):
        legacy = self._legacy('wir172-legacy-normal', 'normal')
        self.assertEqual(auth(legacy).get(URL_EMPLOYES).status_code, 403)

    # ── Les 3 exceptions de lecture élargie, préservées ───────────────────
    def test_annuaire_et_localisation_restent_ouverts(self):
        """XRH28 / ZRH16 — sérialiseurs dédiés, aucun champ sensible."""
        quelconque = self._user('wir172-annuaire', ['crm_voir'])
        api = auth(quelconque)
        self.assertEqual(
            api.get(f'{URL_EMPLOYES}annuaire/').status_code, 200)
        self.assertEqual(
            api.get(f'{URL_EMPLOYES}localisation-du-jour/').status_code, 200)

    def test_compa_ratio_reste_garde_par_salaires_voir(self):
        """XRH16 — un lecteur paie SANS aucun droit RH doit passer."""
        paie = self._user('wir172-paie', ['salaires_voir'])
        resp = auth(paie).get(f'{URL_EMPLOYES}{self.emp.pk}/compa-ratio/')
        # 404 = « poste/bande/salaire manquant » : la GARDE est franchie,
        # c'est le seul point testé ici (jamais 403).
        self.assertIn(resp.status_code, (200, 404))
        sans = self._user('wir172-sans-salaires', ['rh_voir'])
        resp = auth(sans).get(f'{URL_EMPLOYES}{self.emp.pk}/compa-ratio/')
        self.assertEqual(resp.status_code, 403)
