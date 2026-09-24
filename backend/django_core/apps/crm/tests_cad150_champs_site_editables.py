"""CAD150 — T3 : les champs captés par le site sont TOUJOURS éditables, et la
valeur venue du site garde sa PROVENANCE.

Décision fondateur du 21/09/2026 : éditables par la commerciale (un lead
Meta, un walk-in ou un appel entrant ne les a jamais reçus du site), la valeur
du site reste affichée avec « saisie sur le site le … », y compris après un
écrasement fait en connaissance de cause. Contrat partagé :
``apps/crm/contract_samples/lead_provenance_site.json`` (l'écran l'importe).
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import activity, horaires
from apps.crm.models import Lead

User = get_user_model()

ARRIVEE = datetime.datetime(2026, 9, 10, 10, 12, tzinfo=horaires.CASABLANCA)
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_provenance_site.json').read_text(encoding='utf-8'))


class ChampsSitePurTests(SimpleTestCase):

    def test_la_liste_des_champs_du_site(self):
        self.assertEqual(set(Lead.CHAMPS_SITE), {
            'distributeur', 'roof_age', 'ownership', 'project_timeline',
            'financing_intent', 'facility_type', 'roof_type', 'bill_kwh'})

    def test_chaque_ecrasement_laisse_une_trace(self):
        """Sans ligne de modification, la provenance d'un champ écrasé se
        perdrait : TOUS les champs du site sont journalisés."""
        for champ in Lead.CHAMPS_SITE:
            with self.subTest(champ=champ):
                self.assertIn(champ, activity.TRACKED_FIELDS)

    def test_le_contrat_decrit_trois_etats_de_meme_forme(self):
        forme = set(CONTRAT['exemple'])
        for cle in ('exemple_ecrasee', 'exemple_sans_site'):
            self.assertEqual(set(CONTRAT[cle]), forme)
        self.assertEqual(CONTRAT['exemple_sans_site']['provenance_site'], {})


class ChampsSiteApiTests(TestCase):

    def setUp(self):
        with frozen(ARRIVEE):
            self.company = Company.objects.create(nom='CAD150 Solaire',
                                                  slug='cad150-solaire')
            self.acteur = User.objects.create_user(
                username='cad150-resp', password='x',
                role_legacy='responsable', company=self.company)
            self.lead = Lead.objects.create(
                company=self.company, nom='Benali', source=Lead.Source.SITE_WEB,
                ownership='proprietaire', roof_age=12,
                bill_kwh=Decimal('420.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _url(self, lead=None):
        return f'/api/django/crm/leads/{(lead or self.lead).pk}/'

    def test_la_provenance_du_site_est_servie_au_detail(self):
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = CONTRAT['exemple']['provenance_site']
        prov = resp.data['provenance_site']
        self.assertEqual(set(prov), set(attendu))
        for champ, entree in attendu.items():
            with self.subTest(champ=champ):
                self.assertEqual(set(prov[champ]), set(entree))
                self.assertEqual(prov[champ]['valeur'], entree['valeur'])
                self.assertIs(prov[champ]['ecrasee'], False)
                self.assertEqual(
                    datetime.datetime.fromisoformat(prov[champ]['le']),
                    ARRIVEE)

    def test_un_champ_du_site_est_editable_et_garde_sa_provenance(self):
        resp = self.api.patch(self._url(), {'ownership': 'locataire',
                                            'bill_kwh': '380'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.ownership, 'locataire')
        self.assertEqual(self.lead.bill_kwh, Decimal('380'))
        prov = self.api.get(self._url()).data['provenance_site']
        attendu = CONTRAT['exemple_ecrasee']['provenance_site']['ownership']
        self.assertEqual(prov['ownership']['valeur'], attendu['valeur'])
        self.assertIs(prov['ownership']['ecrasee'], True)
        self.assertEqual(prov['bill_kwh']['valeur'], '420.00')
        self.assertIs(prov['bill_kwh']['ecrasee'], True)

    def test_un_lead_hors_site_n_a_aucune_provenance(self):
        autre = Lead.objects.create(company=self.company, nom='Walk-in',
                                    ownership='locataire')
        resp = self.api.get(self._url(autre))
        self.assertEqual(resp.data['provenance_site'],
                         CONTRAT['exemple_sans_site']['provenance_site'])

    def test_la_liste_ne_paie_pas_la_provenance(self):
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = resp.data.get('results', resp.data)
        self.assertTrue(lignes)
        self.assertNotIn('provenance_site', lignes[0])
