"""Tests AUDV06 — exposition REST des devises (XACC17 / XACC18).

Quatre services complets et testés unitairement (`test_taux_devise.py`,
`test_ecarts_change.py`) n'avaient AUCUN ViewSet : la table de taux de change
était inatteignable hors admin Django, si bien que tout document en devise
retombait EN SILENCE sur le repli 1:1 ; aucun écran ne pouvait déclarer un
poste ouvert, constater son écart de change au règlement (gain 733 / perte
633), ni lancer la réévaluation de clôture (écart LATENT 1701/2701 + extourne
au lendemain).

Ce module vérifie la couche REST : les vues ne ré-implémentent AUCUNE règle
(elles routent vers les services existants) et apportent les trois garanties
propres à l'API — refus explicite du second constat, idempotence de la
réévaluation, isolation multi-société — plus la forme du contrat committé.
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
from apps.compta.models import (
    EcritureComptable, ItemOuvertDevise, LigneEcriture, ReevaluationCloture,
    TauxDevise,
)

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'

TAUX = '/api/django/compta/taux-devise/'
POSTES = '/api/django/compta/items-ouverts-devise/'
REEVALUATIONS = '/api/django/compta/reevaluations-cloture/'


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


class TauxDeviseRestTests(TestCase):
    """XACC17 — la table FX devient saisissable depuis un écran."""

    def setUp(self):
        self.co = make_company('audv06-taux', 'AUDV06 Taux')
        services.seed_plan_comptable(self.co)
        self.api = auth(make_user(self.co, 'audv06-taux-user'))

    def test_creation_pose_la_societe_cote_serveur(self):
        resp = self.api.post(TAUX, {
            'devise': 'eur', 'date_taux': '2026-06-01',
            'taux_vers_mad': '10.85',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        taux = TauxDevise.objects.get(id=resp.data['id'])
        self.assertEqual(taux.company_id, self.co.id)
        # La devise est normalisée en majuscules par le sérialiseur.
        self.assertEqual(taux.devise, 'EUR')

    def test_deuxieme_saisie_du_meme_jour_met_a_jour_sans_dupliquer(self):
        self.api.post(TAUX, {'devise': 'EUR', 'date_taux': '2026-06-01',
                             'taux_vers_mad': '10.85'}, format='json')
        resp = self.api.post(TAUX, {'devise': 'EUR', 'date_taux': '2026-06-01',
                                    'taux_vers_mad': '10.90'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            TauxDevise.objects.filter(company=self.co, devise='EUR').count(), 1)
        self.assertEqual(
            TauxDevise.objects.get(company=self.co, devise='EUR').taux_vers_mad,
            Decimal('10.900000'))

    def test_mad_refuse_en_400(self):
        resp = self.api.post(TAUX, {'devise': 'MAD', 'date_taux': '2026-06-01',
                                    'taux_vers_mad': '1'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_taux_non_positif_refuse(self):
        resp = self.api.post(TAUX, {'devise': 'EUR', 'date_taux': '2026-06-01',
                                    'taux_vers_mad': '0'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_isolation_multi_societe(self):
        autre = make_company('audv06-taux-autre', 'AUDV06 Autre')
        TauxDevise.objects.create(
            company=autre, devise='EUR', date_taux=date(2026, 6, 1),
            taux_vers_mad=Decimal('10.85'))
        resp = self.api.get(TAUX)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)


class EcartChangeRestTests(TestCase):
    """XACC18 — l'écart de change RÉALISÉ entre enfin au grand livre."""

    def setUp(self):
        self.co = make_company('audv06-ecart', 'AUDV06 Écart')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.api = auth(make_user(self.co, 'audv06-ecart-user'))

    def _poste(self, **extra):
        corps = {
            'type_document': 'facture_client', 'document_id': 4412,
            'document_reference': 'FAC-2026-0212', 'devise': 'EUR',
            'montant_devise': '12000', 'taux_origine': '10.85',
            'date_origine': '2026-06-01',
        }
        corps.update(extra)
        return self.api.post(POSTES, corps, format='json')

    def test_creation_idempotente_par_document(self):
        premier = self._poste()
        self.assertEqual(premier.status_code, 201, premier.content)
        second = self._poste(taux_origine='99')  # doit être IGNORÉ
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(premier.data['id'], second.data['id'])
        self.assertEqual(
            ItemOuvertDevise.objects.filter(company=self.co).count(), 1)
        # Le taux d'ORIGINE reste figé : c'est la référence de mesure.
        self.assertEqual(
            ItemOuvertDevise.objects.get(company=self.co).taux_origine,
            Decimal('10.850000'))

    def test_document_en_mad_refuse(self):
        resp = self._poste(devise='MAD')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_gain_de_change_credite_733_et_solde_le_poste(self):
        poste = self._poste().data
        resp = self.api.post(
            f'{POSTES}{poste["id"]}/constater-ecart/',
            {'date_reglement': '2026-08-14', 'taux_reglement': '11.10'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['solde'])
        # 12 000 × (11,10 − 10,85) = 3 000 de GAIN.
        self.assertEqual(
            Decimal(resp.data['ecart_change']['difference']), Decimal('3000.00'))
        ecriture = EcritureComptable.objects.get(
            id=resp.data['ecart_change']['ecriture'])
        self.assertTrue(ecriture.est_equilibree)
        self.assertEqual(
            LigneEcriture.objects.get(
                ecriture=ecriture, compte__numero='733').credit,
            Decimal('3000.00'))

    def test_perte_de_change_debite_633(self):
        poste = self._poste(document_id=4413,
                            document_reference='FAC-2026-0213').data
        resp = self.api.post(
            f'{POSTES}{poste["id"]}/constater-ecart/',
            {'date_reglement': '2026-08-14', 'taux_reglement': '10.60'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            Decimal(resp.data['ecart_change']['difference']),
            Decimal('-3000.00'))
        ecriture = EcritureComptable.objects.get(
            id=resp.data['ecart_change']['ecriture'])
        self.assertEqual(
            LigneEcriture.objects.get(
                ecriture=ecriture, compte__numero='633').debit,
            Decimal('3000.00'))

    def test_second_constat_explicitement_refuse(self):
        poste = self._poste().data
        self.api.post(f'{POSTES}{poste["id"]}/constater-ecart/',
                      {'date_reglement': '2026-08-14',
                       'taux_reglement': '11.10'}, format='json')
        second = self.api.post(
            f'{POSTES}{poste["id"]}/constater-ecart/',
            {'date_reglement': '2026-09-14', 'taux_reglement': '12.00'},
            format='json')
        self.assertEqual(second.status_code, 400, second.content)
        self.assertIn('déjà soldé', second.data['detail'])

    def test_date_de_reglement_obligatoire(self):
        poste = self._poste().data
        resp = self.api.post(f'{POSTES}{poste["id"]}/constater-ecart/', {},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_la_reponse_porte_exactement_les_cles_du_contrat(self):
        poste = self._poste().data
        # Variante « non soldé » : le poste AVANT tout règlement.
        self.assertEqual(
            sorted(set(contrat('devise_poste_ouvert', 'exemple_non_solde'))
                   - {'pourquoi'}),
            sorted(poste))
        resp = self.api.post(
            f'{POSTES}{poste["id"]}/constater-ecart/',
            {'date_reglement': '2026-08-14', 'taux_reglement': '11.10'},
            format='json')
        exemple = contrat('devise_poste_ouvert')
        self.assertEqual(sorted(exemple), sorted(resp.data))
        self.assertEqual(sorted(exemple['ecart_change']),
                         sorted(resp.data['ecart_change']))


class ReevaluationClotureRestTests(TestCase):
    """XACC18 — l'écart LATENT de clôture, et son extourne au lendemain."""

    def setUp(self):
        self.co = make_company('audv06-reev', 'AUDV06 Réévaluation')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv06-reev-user')
        self.api = auth(self.user)
        services.enregistrer_item_ouvert_devise(
            self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
            document_id=901, document_reference='FAC-901', devise='EUR',
            montant_devise=Decimal('10000'), taux_origine=Decimal('10.00'),
            date_origine=date(2026, 6, 1))
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 12, 31),
            taux_vers_mad=Decimal('10.50'))

    def test_le_run_poste_l_ecart_latent_et_son_extourne(self):
        resp = self.api.post(
            f'{REEVALUATIONS}lancer/', {'date_cloture': '2026-12-31'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        # 10 000 × (10,50 − 10,00) = 5 000 d'écart latent.
        self.assertEqual(Decimal(resp.data['total_ecart']), Decimal('5000.00'))
        self.assertIsNotNone(resp.data['ecriture'])
        self.assertIsNotNone(resp.data['ecriture_extourne'])
        # L'extourne est datée du LENDEMAIN : l'exercice suivant repart du réel.
        # (Réponse JSON : DRF rend une date en ISO-8601, jamais un `date`.)
        self.assertEqual(resp.data['date_extourne'], '2027-01-01')
        self.assertEqual(len(resp.data['lignes']), 1)

    def test_relancer_la_meme_date_ne_double_pas_l_ecriture(self):
        premier = self.api.post(
            f'{REEVALUATIONS}lancer/', {'date_cloture': '2026-12-31'},
            format='json')
        second = self.api.post(
            f'{REEVALUATIONS}lancer/', {'date_cloture': '2026-12-31'},
            format='json')
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(premier.data['id'], second.data['id'])
        self.assertEqual(premier.data['ecriture'], second.data['ecriture'])
        self.assertEqual(
            ReevaluationCloture.objects.filter(company=self.co).count(), 1)

    def test_date_de_cloture_obligatoire(self):
        resp = self.api.post(f'{REEVALUATIONS}lancer/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_lecture_seule_aucune_creation_directe(self):
        """Un run se LANCE, il ne se saisit pas."""
        resp = self.api.post(
            REEVALUATIONS, {'date_cloture': '2026-12-31'}, format='json')
        self.assertEqual(resp.status_code, 405, resp.content)
