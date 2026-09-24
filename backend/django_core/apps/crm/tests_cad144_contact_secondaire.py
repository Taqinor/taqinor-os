"""CAD144 — un achat de coopérative ou un comité industriel : un contact
SECONDAIRE sur la fiche, et aucune automatisation vers lui.

Done : le champ existe, s'affiche (servi par le sérialiseur de lead, masqué
comme toute PII sans ``client_pii_voir``) et n'entre dans AUCUNE cadence.
Contrat partagé : ``apps/crm/contract_samples/lead_contact_secondaire.json``
(le test écran l'importe).
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import cadence_temps, services, stages
from apps.crm.models import Lead
from apps.crm.serializers import LEAD_PII_FIELDS
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_contact_secondaire.json').read_text(encoding='utf-8'))


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ContactSecondairePurTests(SimpleTestCase):

    def test_le_telephone_secondaire_est_une_pii(self):
        self.assertIn('contact_secondaire_telephone', LEAD_PII_FIELDS)

    def test_la_cadence_ne_voit_aucun_numero_joignable(self):
        """Seul numéro de la fiche = celui du contact secondaire ⇒ la cadence
        n'a RIEN à composer : ce second contact n'entre dans aucune touche."""
        lead = Lead(nom='Coopérative', contact_secondaire_telephone=(
            CONTRAT['corps']['contact_secondaire_telephone']))
        self.assertEqual(cadence_temps.numero_joignable(lead), '')

    def test_le_contrat_decrit_les_deux_etats(self):
        self.assertEqual(sorted(CONTRAT['exemple']),
                         sorted(CONTRAT['exemple_pii_masquee']))
        self.assertIsNone(
            CONTRAT['exemple_pii_masquee']['contact_secondaire_telephone'])


class ContactSecondaireApiTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD144 Coop',
                                              slug='cad144-coop')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.responsable = User.objects.create_user(
            username='cad144-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Coopérative Al Amal',
            stage=stages.CONTACTED, owner=self.responsable,
            telephone='+212661000144')

    def _url(self):
        return f'/api/django/crm/leads/{self.lead.pk}/'

    def test_le_champ_s_enregistre_et_se_relit(self):
        resp = _api(self.responsable).patch(
            self._url(), CONTRAT['corps'], format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        for cle, valeur in CONTRAT['exemple'].items():
            if cle == 'id':
                continue
            with self.subTest(cle=cle):
                self.assertEqual(resp.data[cle], valeur)

    def test_masque_sans_client_pii_voir(self):
        Lead.objects.filter(pk=self.lead.pk).update(**CONTRAT['corps'])
        role = Role.objects.create(company=self.company,
                                   nom='CAD144 sans PII',
                                   permissions=['crm_voir'])
        lecteur = User.objects.create_user(
            username='cad144-lecteur', password='x', role=role,
            company=self.company)
        resp = _api(lecteur).get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = CONTRAT['exemple_pii_masquee']
        for cle in ('contact_secondaire_nom', 'contact_secondaire_telephone',
                    'pii_masked'):
            with self.subTest(cle=cle):
                self.assertEqual(resp.data[cle], attendu[cle])

    def test_n_entre_dans_aucune_cadence(self):
        """Un lead dont le SEUL numéro est celui du contact secondaire ne
        démarre aucune prise de contact, et la dédup téléphone ne le trouve
        pas par ce numéro."""
        seul = Lead.objects.create(
            company=self.company, nom='Comité usine',
            owner=self.responsable,
            contact_secondaire_nom='Technicien de maintenance',
            contact_secondaire_telephone='0662334455')
        services.demarrer_cadence_contact(seul, origine='test')
        self.assertFalse(seul.relance_etapes.exists())
        self.assertEqual(services.find_duplicates_by_contact(
            self.company, phone='0662334455'), [])
