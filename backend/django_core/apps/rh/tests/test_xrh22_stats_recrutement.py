"""Tests XRH22 — Analytics recrutement (délai d'embauche, entonnoir, sources).

Couvre :
* l'entonnoir somme correctement (une candidature à une étape avancée compte
  dans toutes les étapes antérieures) ;
* les sources sont classées par taux d'embauche décroissant, division par
  zéro gardée ;
* le filtre de période ;
* isolation société.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import Candidature, OuverturePoste

User = get_user_model()

STATS_URL = '/api/django/rh/recrutement/statistiques/'


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


class StatsRecrutementTests(TestCase):
    def setUp(self):
        self.co = make_company('stats-a', 'A')
        self.rh = make_user(self.co, 'stats-rh')
        self.ouv1 = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose')
        self.ouv2 = OuverturePoste.objects.create(
            company=self.co, intitule='Ingénieur BE')

    def test_entonnoir_somme_correctement(self):
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Reçu seul',
            etape=Candidature.Etape.RECU, source='LinkedIn',
            date_candidature=date(2026, 1, 5))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Présélectionné',
            etape=Candidature.Etape.PRESELECTION, source='LinkedIn',
            date_candidature=date(2026, 1, 6))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Offre',
            etape=Candidature.Etape.OFFRE, source='ANAPEC',
            date_candidature=date(2026, 1, 7))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Rejeté',
            etape=Candidature.Etape.REJETE, source='ANAPEC',
            date_candidature=date(2026, 1, 8))

        data = selectors.stats_recrutement(self.co)
        self.assertEqual(data['entonnoir']['recu'], 3)
        self.assertEqual(data['entonnoir']['preselection'], 2)
        self.assertEqual(data['entonnoir']['entretien'], 1)
        self.assertEqual(data['entonnoir']['offre'], 1)
        self.assertEqual(data['entonnoir']['embauche'], 0)
        self.assertEqual(data['entonnoir']['rejete'], 1)

    def test_sources_classees_par_taux_embauche_division_zero_gardee(self):
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='A1',
            etape=Candidature.Etape.EMBAUCHE, source='Cooptation',
            date_candidature=date(2026, 1, 1))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='A2',
            etape=Candidature.Etape.RECU, source='Cooptation',
            date_candidature=date(2026, 1, 2))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='B1',
            etape=Candidature.Etape.RECU, source='LinkedIn',
            date_candidature=date(2026, 1, 2))

        data = selectors.stats_recrutement(self.co)
        by_source = {row['source']: row for row in data['sources']}
        self.assertEqual(by_source['Cooptation']['candidatures'], 2)
        self.assertEqual(by_source['Cooptation']['embauches'], 1)
        self.assertEqual(by_source['Cooptation']['taux_embauche_pct'], 50.0)
        self.assertEqual(by_source['LinkedIn']['taux_embauche_pct'], 0.0)
        # Classé décroissant : Cooptation (50%) avant LinkedIn (0%).
        self.assertEqual(data['sources'][0]['source'], 'Cooptation')

    def test_delai_embauche_moyen(self):
        c = Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Rapide',
            etape=Candidature.Etape.EMBAUCHE, source='LinkedIn',
            date_candidature=date(2026, 1, 1))
        # ``date_modification`` est ``auto_now`` : passer par ``.save()``
        # réécrase toujours la valeur avec l'horodatage réel. Pour fixer une
        # date de test, il faut contourner via ``update()`` (bypass
        # ``auto_now``), même technique que ``test_xrh24_retention_candidatures``.
        Candidature.objects.filter(pk=c.pk).update(
            date_modification=c.date_modification.replace(
                year=2026, month=1, day=11))
        c.refresh_from_db()

        data = selectors.stats_recrutement(self.co)
        self.assertEqual(data['delai_embauche_moyen_jours'], 10.0)

    def test_delai_embauche_none_sans_embauche(self):
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Reçu',
            etape=Candidature.Etape.RECU, date_candidature=date(2026, 1, 1))
        data = selectors.stats_recrutement(self.co)
        self.assertIsNone(data['delai_embauche_moyen_jours'])

    def test_candidatures_par_ouverture(self):
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='X1',
            date_candidature=date(2026, 1, 1))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='X2',
            date_candidature=date(2026, 1, 2))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv2, nom='Y1',
            date_candidature=date(2026, 1, 3))

        data = selectors.stats_recrutement(self.co)
        by_ouv = {row['ouverture_id']: row['nb']
                  for row in data['candidatures_par_ouverture']}
        self.assertEqual(by_ouv[self.ouv1.id], 2)
        self.assertEqual(by_ouv[self.ouv2.id], 1)

    def test_filtre_periode(self):
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Dedans',
            date_candidature=date(2026, 3, 15))
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='Dehors',
            date_candidature=date(2026, 6, 1))

        data = selectors.stats_recrutement(
            self.co, debut=date(2026, 3, 1), fin=date(2026, 3, 31))
        total = sum(row['nb'] for row in data['candidatures_par_ouverture'])
        self.assertEqual(total, 1)

    def test_endpoint_et_isolation_societe(self):
        Candidature.objects.create(
            company=self.co, ouverture=self.ouv1, nom='A',
            etape=Candidature.Etape.EMBAUCHE, source='LinkedIn',
            date_candidature=date(2026, 1, 1))

        resp = auth(self.rh).get(STATS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['entonnoir']['embauche'], 1)

        co_b = make_company('stats-b', 'B')
        rh_b = make_user(co_b, 'stats-rh-b')
        resp_b = auth(rh_b).get(STATS_URL)
        self.assertEqual(resp_b.status_code, 200, resp_b.data)
        self.assertEqual(resp_b.data['entonnoir']['embauche'], 0)
        self.assertEqual(resp_b.data['candidatures_par_ouverture'], [])
