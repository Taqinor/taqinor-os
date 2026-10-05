"""CIQ402 — client « entreprise » : siège, personne à l'attention de, TVA
récupérable, et ``identite_entreprise`` servie (contrat CIQ8
``client_entreprise.json``, D-CIQ-11).

Écart assumé avec le libellé de la tâche (« un particulier sert null ») : le
contrat partagé (``identite_entreprise.regle``) fige pour un particulier la
forme {type_client: 'particulier', complete: true, manquants: [], requis_pour
vide} — c'est elle qui est servie (PACT10 : le contrat fait foi).

Run :
    python manage.py test apps.crm.tests_ciq402_client_entreprise -v 2
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, identite_entreprise

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'client_entreprise.json').read_text(encoding='utf-8'))


def _identite(**kw):
    base = dict(entreprise=True, raison_sociale='X SARL',
                raison_a_confirmer=False, ice='000000000000000', rc='1',
                if_fiscal='2', adresse_siege='', adresse='Site')
    base.update(kw)
    return identite_entreprise(**base)


class BlocPur(SimpleTestCase):
    def test_entreprise_sans_ice(self):
        bloc = _identite(ice='')
        self.assertEqual(bloc['manquants'], ['ice'])
        self.assertEqual(bloc['requis_pour']['facture'], ['ice'])
        self.assertEqual(bloc['requis_pour']['devis'], [])
        self.assertFalse(bloc['complete'])

    def test_exemples_du_contrat(self):
        for cle in ('exemple', 'exemple_nom_propre'):
            ex = CONTRAT[cle]
            bloc = identite_entreprise(
                entreprise=True, raison_sociale=ex['nom'],
                raison_a_confirmer=ex['raison_sociale_a_confirmer'],
                ice=ex['ice'], rc=ex['rc'], if_fiscal=ex['if_fiscal'],
                adresse_siege=ex['adresse_siege'], adresse=ex['adresse'])
            self.assertEqual(bloc, ex['identite_entreprise'], cle)

    def test_siege_manquant_seulement_sans_aucune_adresse(self):
        self.assertNotIn('adresse_siege', _identite()['manquants'])
        self.assertIn('adresse_siege',
                      _identite(adresse='', adresse_siege='')['manquants'])

    def test_particulier_forme_du_contrat(self):
        bloc = identite_entreprise(
            entreprise=False, raison_sociale='', raison_a_confirmer=False,
            ice='', rc='', if_fiscal='', adresse_siege='', adresse='')
        self.assertEqual(bloc, {
            'type_client': 'particulier', 'complete': True, 'manquants': [],
            'requis_pour': {'devis': [], 'acceptation_en_ligne': [],
                            'facture': []}})


class ServiParLApi(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq402-co', defaults={'nom': 'CIQ402 Co'})
        self.autre, _ = Company.objects.get_or_create(
            slug='ciq402-autre', defaults={'nom': 'CIQ402 Autre'})
        self.user = User.objects.create_user(
            username='ciq402_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        ex = CONTRAT['exemple']
        self.client_ent = Client.objects.create(
            company=self.company, nom=ex['nom'], type_client='entreprise',
            ice=ex['ice'], rc=ex['rc'], if_fiscal=ex['if_fiscal'],
            adresse=ex['adresse'], adresse_siege=ex['adresse_siege'],
            contact_nom=ex['contact_nom'],
            contact_fonction=ex['contact_fonction'],
            tva_recuperable=ex['tva_recuperable'])

    def _url(self, client):
        return f'/api/django/crm/clients/{client.id}/'

    def test_la_sortie_egale_l_exemple_du_contrat(self):
        lu = self.api.get(self._url(self.client_ent)).data
        for cle, valeur in CONTRAT['exemple'].items():
            if cle == 'id':
                continue
            self.assertEqual(lu[cle], valeur, cle)

    def test_sans_ice(self):
        self.client_ent.ice = ''
        self.client_ent.save()
        bloc = self.api.get(self._url(self.client_ent)).data[
            'identite_entreprise']
        self.assertEqual(bloc['manquants'], ['ice', 'rc', 'if_fiscal'])
        self.assertEqual(bloc['requis_pour']['facture'], ['ice'])

    def test_particulier(self):
        part = Client.objects.create(company=self.company, nom='Alaoui')
        bloc = self.api.get(self._url(part)).data['identite_entreprise']
        self.assertEqual(bloc['type_client'], 'particulier')
        self.assertEqual(bloc['manquants'], [])

    def test_patch_puis_get_identiques(self):
        corps = {'adresse_siege': '1 rue du Siège, Casablanca',
                 'contact_nom': 'Karim', 'contact_fonction': 'DAF',
                 'tva_recuperable': 'non'}
        resp = self.api.patch(self._url(self.client_ent), corps,
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lu = self.api.get(self._url(self.client_ent)).data
        for cle, valeur in corps.items():
            self.assertEqual(lu[cle], valeur, cle)
        avant = lu
        self.api.patch(self._url(self.client_ent), {}, format='json')
        apres = self.api.get(self._url(self.client_ent)).data
        for cle in corps:
            self.assertEqual(apres[cle], avant[cle], cle)

    def test_lecture_filtree_par_societe(self):
        etranger = Client.objects.create(
            company=self.autre, nom='Ailleurs SA', type_client='entreprise')
        self.assertEqual(self.api.get(self._url(etranger)).status_code, 404)

    def test_le_detail_du_lead_sert_le_bloc(self):
        lead = Lead.objects.create(
            company=self.company, nom='Alaoui', societe='Hôtel Atlas',
            type_installation='commercial', ice='000000000000000')
        lu = self.api.get(f'/api/django/crm/leads/{lead.id}/').data
        self.assertEqual(lu['identite_entreprise']['type_client'],
                         'entreprise')
        self.assertEqual(lu['identite_entreprise']['manquants'],
                         ['rc', 'if_fiscal', 'adresse_siege'])
        residentiel = Lead.objects.create(company=self.company, nom='Villa')
        lu = self.api.get(f'/api/django/crm/leads/{residentiel.id}/').data
        self.assertEqual(lu['identite_entreprise']['type_client'],
                         'particulier')
