"""CAD158 — « Votre facture, c'est pour un mois ou pour deux ? »

Le moteur lit ``facture_hiver`` comme un montant MENSUEL : un montant
bimestriel faussait tout l'aval. Décision fondateur du 21/09/2026 (Q24) : le
montant est ramené au mois AU MOMENT DE LA SAISIE, aucun champ « périodicité »
n'est stocké, et la valeur normalisée est celle qu'on relit.

Done : ``facture_hiver`` porte sa question en ``help_text`` ; un montant
déclaré bimestriel est enregistré au mois. Contrat partagé :
``apps/crm/contract_samples/lead_facture_periodicite.json`` (l'écran
l'importe).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import services
from apps.crm.models import Lead

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_facture_periodicite.json').read_text(encoding='utf-8'))


class PeriodicitePureTests(SimpleTestCase):

    def test_la_question_vit_dans_le_help_text(self):
        aide = str(Lead._meta.get_field('facture_hiver').help_text)
        self.assertIn('un mois ou deux mois', aide)
        self.assertIn('MENSUEL', aide)

    def test_un_montant_bimestriel_est_ramene_au_mois(self):
        self.assertEqual(
            services.facture_au_mois(CONTRAT['corps']['facture_hiver'],
                                     CONTRAT['corps']['facture_periodicite']),
            Decimal(CONTRAT['exemple']['facture_hiver']))

    def test_arrondi_au_centime_moitie_vers_le_haut(self):
        self.assertEqual(services.facture_au_mois('1301', 'bimestrielle'),
                         Decimal('650.50'))
        self.assertEqual(services.facture_au_mois('1301.01', 'bimestrielle'),
                         Decimal('650.51'))

    def test_mensuelle_ne_change_rien_et_rien_n_est_invente(self):
        self.assertEqual(services.facture_au_mois('650', 'mensuelle'),
                         Decimal('650.00'))
        self.assertIsNone(services.facture_au_mois(None, 'bimestrielle'))

    def test_une_periode_inconnue_est_refusee_en_nommant_le_champ(self):
        self.assertEqual(
            services.refus_periodicite_facture('trimestrielle'),
            CONTRAT['exemple_erreur_periodicite']['facture_periodicite'][0])
        self.assertIsNone(services.refus_periodicite_facture('bimestrielle'))


class PeriodiciteApiTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD158 Solaire',
                                              slug='cad158-solaire')
        self.acteur = User.objects.create_user(
            username='cad158-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Alaoui')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _patch(self, corps):
        return self.api.patch(f'/api/django/crm/leads/{self.lead.pk}/',
                              corps, format='json')

    def test_un_montant_bimestriel_est_enregistre_au_mois(self):
        resp = self._patch(CONTRAT['corps'])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['facture_hiver'],
                         CONTRAT['exemple']['facture_hiver'])
        # Jamais stocké ni renvoyé : aucun champ « périodicité ».
        self.assertNotIn('facture_periodicite', resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.facture_hiver,
                         Decimal(CONTRAT['exemple']['facture_hiver']))

    def test_la_periode_sans_montant_est_refusee_en_nommant_le_champ(self):
        resp = self._patch({'facture_periodicite': 'bimestrielle'})
        self.assertEqual(resp.status_code, 400)
        # YAPIC3 (core.exceptions.taqinor_exception_handler) ajoute
        # TOUJOURS une enveloppe `error` additive sur ce endpoint standard
        # (raise DRFValidationError, pas une Response construite à la main) :
        # on compare le champ métier du contrat, pas le dict entier — même
        # patron que tests_mry22_motif_obligatoire.py pour ce même endpoint.
        self.assertEqual(resp.data['facture_periodicite'],
                         CONTRAT['exemple_erreur_sans_montant']['facture_periodicite'])

    def test_une_periode_inconnue_ne_touche_rien(self):
        resp = self._patch({'facture_hiver': '900',
                            'facture_periodicite': 'trimestrielle'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['facture_periodicite'],
                         CONTRAT['exemple_erreur_periodicite']['facture_periodicite'])
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.facture_hiver)
