"""VTA16 — recherche lead MINIMALE servie par l'app Visites.

Ce que le test prouve :

* **la porte est sur l'ENDPOINT** — sans ``visites_valider``, un commercial
  terrain (rôle VTA4) reçoit 403 : un écran qui cacherait le champ ne
  protégerait rien, et sans cette garde n'importe quel terrain énumérerait le
  fichier leads au moteur de recherche ;
* **la portée société est SERVEUR** — le lead d'un autre locataire n'est jamais
  renvoyé, même en tapant son nom exact ;
* **la forme est EXACTEMENT celle du contrat** — ``{id, nom, ville,
  telephone}`` et rien d'autre : ni email, ni étape de pipeline, ni montant ;
* **une recherche vide ne renvoie RIEN** — on n'énumère pas l'annuaire quand
  l'utilisateur n'a pas tapé.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/visites/leads-recherche/'
TERRAIN = ['visites_voir', 'visites_creer', 'visites_modifier']
BUREAU = TERRAIN + ['visites_valider']

CONTRAT = (Path(__file__).resolve().parents[1]
           / 'contract_samples' / 'leads_recherche.json')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LeadsRechercheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='VTA16 Solaire',
                                             slug='vta16-a')
        cls.autre = Company.objects.create(nom='VTA16 Concurrent',
                                           slug='vta16-b')
        cls.terrain = cls._user(cls.company, 'vta16-terrain', TERRAIN)
        cls.bureau = cls._user(cls.company, 'vta16-bureau', BUREAU)
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Bennani', prenom='Karim',
            ville='Bouskoura', telephone='0600112233',
            email='bennani@example.ma')
        cls.lead_autre = Lead.objects.create(
            company=cls.autre, nom='Bennani', ville='Rabat',
            telephone='0611223344')

    @staticmethod
    def _user(company, username, permissions):
        role = Role.objects.create(company=company, nom=f'role-{username}',
                                   permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=company,
            role_legacy='normal', role=role)

    # ── La porte ────────────────────────────────────────────────────────────
    def test_sans_visites_valider_est_refuse(self):
        resp = auth(self.terrain).get(URL, {'q': 'Ben'})
        self.assertEqual(resp.status_code, 403)

    def test_anonyme_refuse(self):
        resp = APIClient().get(URL, {'q': 'Ben'})
        self.assertIn(resp.status_code, (401, 403))

    # ── La portée société ───────────────────────────────────────────────────
    def test_ne_renvoie_jamais_le_lead_d_une_autre_societe(self):
        resp = auth(self.bureau).get(URL, {'q': 'Bennani'})
        self.assertEqual(resp.status_code, 200)
        ids = [ligne['id'] for ligne in resp.data['results']]
        self.assertEqual(ids, [self.lead.id])
        self.assertNotIn(self.lead_autre.id, ids)

    # ── La forme ────────────────────────────────────────────────────────────
    def test_champs_exacts_du_contrat_et_rien_d_autre(self):
        resp = auth(self.bureau).get(URL, {'q': 'Ben'})
        ligne = resp.data['results'][0]
        self.assertEqual(set(ligne), {'id', 'nom', 'ville', 'telephone'})
        self.assertEqual(ligne['nom'], 'Bennani')
        self.assertEqual(ligne['ville'], 'Bouskoura')
        self.assertEqual(ligne['telephone'], '0600112233')

    def test_la_forme_servie_est_celle_du_contrat_committe(self):
        attendu = json.loads(CONTRAT.read_text(encoding='utf-8'))
        exemple = attendu['exemple']['results'][0]
        resp = auth(self.bureau).get(URL, {'q': 'Ben'})
        self.assertEqual(set(resp.data), set(attendu['exemple']))
        self.assertEqual(set(resp.data['results'][0]), set(exemple))

    def test_recherche_par_telephone(self):
        resp = auth(self.bureau).get(URL, {'q': '0011'})
        self.assertEqual([ligne['id'] for ligne in resp.data['results']],
                         [self.lead.id])

    def test_terme_vide_ne_renvoie_rien(self):
        for terme in ('', '   '):
            resp = auth(self.bureau).get(URL, {'q': terme})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data['results'], [])

    def test_limite_plafonnee(self):
        for i in range(12):
            Lead.objects.create(company=self.company, nom=f'Zahra {i}')
        resp = auth(self.bureau).get(URL, {'q': 'Zahra'})
        self.assertEqual(len(resp.data['results']), 10)
        resp = auth(self.bureau).get(URL, {'q': 'Zahra', 'limit': 3})
        self.assertEqual(len(resp.data['results']), 3)

    def test_lead_supprime_est_hors_resultat(self):
        supprime = Lead.objects.create(company=self.company, nom='Ben Corbeille')
        supprime.soft_delete(self.bureau)
        ids = [ligne['id'] for ligne in
               auth(self.bureau).get(URL, {'q': 'Ben'}).data['results']]
        self.assertNotIn(supprime.id, ids)
