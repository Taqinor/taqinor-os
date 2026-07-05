"""Tests XQHS26 — Veille réglementaire QHSE Maroc (revue périodique assistée).

Version SOBRE sans dépendance externe (AUCUN scraping, règle CLAUDE.md #5) :
seule la CADENCE de revue est automatisée. Couvre :

* création : ``date_prochaine_revue`` initialisée (cadence par défaut = 90
  jours / trimestrielle) ;
* ``generer-revues-dues`` : génère une revue ``a_faire`` pour une veille due,
  idempotent (ré-appel ne duplique rien tant qu'une revue est ouverte) ;
* ``conclure`` : conclusion applicable/non_applicable, avance
  ``date_prochaine_revue`` du parent, refuse une conclusion invalide ;
* conclusion ``applicable`` lie/instancie le registre légal (XQHS8,
  ``ConformiteEnvironnementale``), idempotent (jamais deux entrées) ;
* scoping société (404 hors société) ; garde-fou de rôle.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    ConformiteEnvironnementale, RevueVeilleReglementaire, VeilleReglementaire,
)

User = get_user_model()

VEILLES_URL = '/api/django/qhse/veilles-reglementaires/'
REVUES_URL = '/api/django/qhse/revues-veille/'


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


class VeilleReglementaireCreationTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs26-creation', 'CoXqhs26Creation')
        self.user = make_user(self.company, 'xqhs26-resp')
        self.client_api = auth_client(self.user)

    def test_creation_initialise_prochaine_revue_trimestrielle(self):
        resp = self.client_api.post(
            VEILLES_URL,
            {'texte_suivi': 'Loi 82-21 (net-billing)', 'source': 'BO'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        veille = VeilleReglementaire.objects.get(id=resp.data['id'])
        self.assertEqual(veille.company, self.company)
        self.assertIsNotNone(veille.date_prochaine_revue)
        self.assertEqual(veille.cadence_jours, 90)
        attendu = date.today() + timedelta(days=90)
        self.assertEqual(veille.date_prochaine_revue, attendu)

    def test_creation_cadence_personnalisee(self):
        resp = self.client_api.post(
            VEILLES_URL,
            {'texte_suivi': 'Loi 28-00 déchets', 'cadence_jours': 30},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        veille = VeilleReglementaire.objects.get(id=resp.data['id'])
        attendu = date.today() + timedelta(days=30)
        self.assertEqual(veille.date_prochaine_revue, attendu)

    def test_role_non_responsable_refuse(self):
        autre = make_user(self.company, 'xqhs26-user', role='normal')
        resp = auth_client(autre).post(
            VEILLES_URL, {'texte_suivi': 'X'}, format='json')
        self.assertEqual(resp.status_code, 403)


class GenererRevuesDuesTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs26-gen', 'CoXqhs26Gen')
        self.user = make_user(self.company, 'xqhs26-gen-resp')
        self.client_api = auth_client(self.user)

    def _make_veille(self, prochaine):
        return VeilleReglementaire.objects.create(
            company=self.company, texte_suivi='Texte suivi',
            date_prochaine_revue=prochaine)

    def test_genere_une_revue_pour_veille_due(self):
        veille = self._make_veille(date.today() - timedelta(days=1))
        resp = self.client_api.post(
            VEILLES_URL + 'generer-revues-dues/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['generees'], 1)
        revue = RevueVeilleReglementaire.objects.get(veille=veille)
        self.assertEqual(
            revue.conclusion, RevueVeilleReglementaire.Conclusion.A_FAIRE)

    def test_ne_genere_rien_pour_veille_pas_encore_due(self):
        self._make_veille(date.today() + timedelta(days=30))
        resp = self.client_api.post(
            VEILLES_URL + 'generer-revues-dues/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['generees'], 0)

    def test_idempotent_ne_duplique_pas_revue_ouverte(self):
        self._make_veille(date.today() - timedelta(days=1))
        self.client_api.post(VEILLES_URL + 'generer-revues-dues/', {}, format='json')
        resp2 = self.client_api.post(
            VEILLES_URL + 'generer-revues-dues/', {}, format='json')
        self.assertEqual(resp2.data['generees'], 0)
        self.assertEqual(RevueVeilleReglementaire.objects.count(), 1)


class ConclureRevueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs26-concl', 'CoXqhs26Concl')
        self.other_company = make_company('co-xqhs26-concl-2', 'CoXqhs26Concl2')
        self.user = make_user(self.company, 'xqhs26-concl-resp')
        self.client_api = auth_client(self.user)
        self.veille = VeilleReglementaire.objects.create(
            company=self.company, texte_suivi='Loi 82-21',
            source='BO 7400',
            date_prochaine_revue=date.today())
        self.revue = RevueVeilleReglementaire.objects.create(
            company=self.company, veille=self.veille,
            date_echeance=date.today())

    def test_conclusion_invalide_refusee(self):
        resp = self.client_api.post(
            f'{REVUES_URL}{self.revue.pk}/conclure/',
            {'conclusion': 'peut-etre'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_conclusion_non_applicable_pas_de_registre(self):
        resp = self.client_api.post(
            f'{REVUES_URL}{self.revue.pk}/conclure/',
            {'conclusion': 'non_applicable'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.veille.refresh_from_db()
        self.assertIsNone(self.veille.registre_conformite_id)
        self.assertEqual(
            self.veille.date_derniere_revue, date.today())
        self.assertGreater(self.veille.date_prochaine_revue, date.today())

    def test_conclusion_applicable_cree_registre_legal(self):
        resp = self.client_api.post(
            f'{REVUES_URL}{self.revue.pk}/conclure/',
            {'conclusion': 'applicable', 'impact_evalue': 'Impact tarifaire'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.veille.refresh_from_db()
        self.assertIsNotNone(self.veille.registre_conformite_id)
        registre = ConformiteEnvironnementale.objects.get(
            id=self.veille.registre_conformite_id)
        self.assertEqual(registre.intitule, 'Loi 82-21')
        self.assertEqual(registre.company, self.company)

    def test_conclusion_applicable_idempotente_ne_duplique_pas_registre(self):
        self.client_api.post(
            f'{REVUES_URL}{self.revue.pk}/conclure/',
            {'conclusion': 'applicable'}, format='json')
        self.veille.refresh_from_db()
        premier_registre_id = self.veille.registre_conformite_id

        # Une deuxième revue applicable ne doit PAS créer un second registre.
        revue2 = RevueVeilleReglementaire.objects.create(
            company=self.company, veille=self.veille,
            date_echeance=date.today())
        self.client_api.post(
            f'{REVUES_URL}{revue2.pk}/conclure/',
            {'conclusion': 'applicable'}, format='json')
        self.veille.refresh_from_db()
        self.assertEqual(self.veille.registre_conformite_id, premier_registre_id)
        self.assertEqual(ConformiteEnvironnementale.objects.filter(
            company=self.company).count(), 1)

    def test_revue_hors_societe_404(self):
        autre_user = make_user(self.other_company, 'xqhs26-autre-resp')
        resp = auth_client(autre_user).post(
            f'{REVUES_URL}{self.revue.pk}/conclure/',
            {'conclusion': 'applicable'}, format='json')
        self.assertEqual(resp.status_code, 404)
