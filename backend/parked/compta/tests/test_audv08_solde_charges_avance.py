"""Tests AUDV08 — le solde 3491 restant à étaler devient lisible (XACC15).

`selectors.solde_charges_constatees_avance` était complet et testé au niveau
sélecteur, sans AUCUN appelant HTTP : l'écran comptait bien « n/12 dotations
postées » par ligne, mais personne ne pouvait lire le MONTANT encore
immobilisé au compte 3491 — le seul chiffre qui se rapproche du bilan, et
celui que le comptable doit justifier à la clôture.

(L'autre moitié d'AUDV08 — création et évaluation d'un état personnalisé
XACC19 — était DÉJÀ atteignable de bout en bout, service → ViewSet
`etats-personnalises/` → `EtatsPersonnalisesPage`, avec ses tests des deux
côtés : rien n'y a été retouché, voir `test_wir279_emprunts_etats_rest.py`.)
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'
URL = '/api/django/compta/charges-avance/solde/'


def contrat(nom, variante='exemple'):
    return json.loads(
        (CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))[variante]


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SoldeChargesAvanceRestTests(TestCase):
    def setUp(self):
        self.co = make_company('audv08', 'AUDV08 CCA')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv08-user')
        self.api = auth(self.user)
        self.charge = services.etaler_charge_avance(
            self.co, montant_total=Decimal('12000'),
            date_debut=date(2026, 1, 1), nb_mois=12,
            libelle='Assurance annuelle flotte', user=self.user)

    def test_avant_tout_postage_tout_reste_a_etaler(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['total_restant'], Decimal('12000.00'))
        self.assertEqual(len(resp.data['charges']), 1)
        self.assertEqual(resp.data['charges'][0]['dote'], Decimal('0'))

    def test_seules_les_dotations_POSTEES_diminuent_le_solde(self):
        """Une dotation générée mais non postée n'a pas bougé le grand livre."""
        avant = self.api.get(URL).data['total_restant']
        dotations = list(self.charge.dotations.order_by('numero')[:3])
        for dotation in dotations:
            services.poster_dotation_etalement(dotation, user=self.user)
        apres = self.api.get(URL).data
        self.assertEqual(
            apres['total_restant'],
            avant - sum((d.montant for d in dotations), Decimal('0')))
        self.assertEqual(apres['charges'][0]['dote'], Decimal('3000.00'))
        self.assertEqual(apres['charges'][0]['solde_restant'],
                         Decimal('9000.00'))

    def test_le_solde_se_lit_a_une_date(self):
        """Une dotation postée APRÈS `date_fin` ne compte pas encore."""
        for dotation in self.charge.dotations.order_by('numero')[:3]:
            services.poster_dotation_etalement(dotation, user=self.user)
        # Les dotations tombent au 1er de chaque mois à partir de 2026-01-01 :
        # borner au 31/01 n'en laisse qu'UNE dans le champ de lecture.
        resp = self.api.get(URL, {'date_fin': '2026-01-31'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['charges'][0]['dote'], Decimal('1000.00'))
        self.assertEqual(resp.data['charges'][0]['solde_restant'],
                         Decimal('11000.00'))

    def test_date_fin_invalide_est_un_400_francais(self):
        resp = self.api.get(URL, {'date_fin': 'pas-une-date'})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('date', resp.data['detail'].lower())

    def test_la_reponse_porte_exactement_les_cles_du_contrat(self):
        resp = self.api.get(URL)
        # `detail` est le canal d'ERREUR : au contrat (la garde unifie les
        # branches de la vue), absent de la réponse de succès.
        exemple = contrat('charges_avance_solde')
        self.assertEqual(sorted(set(exemple) - {'detail'}), sorted(resp.data))
        self.assertIsNone(exemple['detail'])
        self.assertEqual(sorted(exemple['charges'][0]),
                         sorted(resp.data['charges'][0]))

    def test_variante_vide_du_contrat(self):
        vide = make_company('audv08-vide', 'AUDV08 Vide')
        api = auth(make_user(vide, 'audv08-vide-user'))
        resp = api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            sorted(set(contrat('charges_avance_solde', 'exemple_vide'))
                   - {'detail'}),
            sorted(resp.data))
        self.assertEqual(resp.data['charges'], [])

    def test_scopee_par_societe(self):
        autre = make_company('audv08-autre', 'AUDV08 Autre')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        services.etaler_charge_avance(
            autre, montant_total=Decimal('99999'),
            date_debut=date(2026, 1, 1), nb_mois=3, libelle='Hors société')
        resp = self.api.get(URL)
        self.assertEqual(len(resp.data['charges']), 1)
        self.assertEqual(resp.data['total_restant'], Decimal('12000.00'))
