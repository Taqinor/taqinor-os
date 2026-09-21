"""Tests AUDV07 — exposition REST du postage des dotations dérogatoires.

`services.poster_dotation_derogatoire` (XACC16) était complet et testé au
niveau service, sans AUCUN appelant : le plan fiscal se générait bien depuis
l'écran Immobilisations (action `plan-fiscal`, déjà branchée) avec ses
différences par exercice, mais AUCUNE ne pouvait jamais être passée au grand
livre. La provision réglementée 1351 n'était donc jamais constituée — l'écart
entre amortissement fiscal et amortissement comptable restait un chiffre
d'écran, invisible du bilan.

Ce module couvre la couche REST des DEUX moitiés d'AUDV07 : la génération du
plan fiscal (jusqu'ici testée au seul niveau service, jamais par l'API) et le
postage, avec ses garanties propres à la vue — re-post refusé, exercice
inconnu refusé, différence nulle sans écriture, isolation multi-société.
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
    EcritureComptable, Immobilisation, LigneEcriture, PlanAmortissement,
)

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'


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


class PlanFiscalEtPostageRestTests(TestCase):
    def setUp(self):
        self.co = make_company('audv07', 'AUDV07 Dérogatoire')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = make_user(self.co, 'audv07-user')
        self.api = auth(self.user)
        self.immo = Immobilisation.objects.create(
            company=self.co, libelle='Machine industrielle',
            categorie=Immobilisation.Categorie.MATERIEL,
            cout=Decimal('100000'), taux_tva=Decimal('20.00'),
            date_acquisition=date(2026, 1, 1))
        services.generer_plan_amortissement(
            self.immo, mode=PlanAmortissement.Mode.LINEAIRE, duree_annees=5,
            base_amortissable=Decimal('100000'), date_debut=date(2026, 1, 1))

    def _url(self, suffixe, immo=None):
        return (f'/api/django/compta/immobilisations/'
                f'{(immo or self.immo).id}/{suffixe}/')

    def _generer_plan_fiscal(self):
        return self.api.post(self._url('plan-fiscal'), {
            'mode': PlanAmortissement.Mode.DEGRESSIF, 'duree_annees': 5,
            'coefficient_degressif': '2.00',
        }, format='json')

    def test_generation_du_plan_fiscal_par_l_api(self):
        resp = self._generer_plan_fiscal()
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['dotations_derogatoires'])

    def test_postage_dote_la_provision_reglementee(self):
        plan = self._generer_plan_fiscal().data
        # Le 1er exercice du dégressif dote plus que le linéaire : différence
        # POSITIVE, donc débit 65941 / crédit 1351.
        annee = plan['dotations_derogatoires'][0]['annee']
        resp = self.api.post(
            self._url('poster-dotation-derogatoire'), {'annee': annee},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['posted'])
        self.assertGreater(Decimal(resp.data['difference']), 0)
        ecriture = EcritureComptable.objects.get(id=resp.data['ecriture_id'])
        self.assertTrue(ecriture.est_equilibree)
        self.assertEqual(
            LigneEcriture.objects.get(
                ecriture=ecriture, compte__numero='1351').credit,
            Decimal(resp.data['difference']))

    def test_la_reponse_porte_exactement_les_cles_du_contrat(self):
        plan = self._generer_plan_fiscal().data
        annee = plan['dotations_derogatoires'][0]['annee']
        resp = self.api.post(
            self._url('poster-dotation-derogatoire'), {'annee': annee},
            format='json')
        # `detail` est le canal d'ERREUR : au contrat (la garde unifie les
        # branches de la vue), absent de la réponse de succès.
        exemple = contrat('dotation_derogatoire_poster')
        self.assertEqual(sorted(set(exemple) - {'detail'}), sorted(resp.data))

    def test_re_post_explicitement_refuse(self):
        plan = self._generer_plan_fiscal().data
        annee = plan['dotations_derogatoires'][0]['annee']
        self.api.post(self._url('poster-dotation-derogatoire'),
                      {'annee': annee}, format='json')
        second = self.api.post(
            self._url('poster-dotation-derogatoire'), {'annee': annee},
            format='json')
        self.assertEqual(second.status_code, 400, second.content)
        self.assertIn('déjà', second.data['detail'])

    def test_exercice_inconnu_refuse(self):
        self._generer_plan_fiscal()
        resp = self.api.post(
            self._url('poster-dotation-derogatoire'), {'annee': 2999},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_sans_plan_fiscal_le_postage_est_refuse(self):
        resp = self.api.post(
            self._url('poster-dotation-derogatoire'), {'annee': 2026},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('plan fiscal', resp.data['detail'])

    def test_scopee_par_societe(self):
        autre = make_company('audv07-autre', 'AUDV07 Autre')
        immo_autre = Immobilisation.objects.create(
            company=autre, libelle='Hors société',
            categorie=Immobilisation.Categorie.MATERIEL,
            cout=Decimal('1000'), date_acquisition=date(2026, 1, 1))
        resp = self.api.post(
            self._url('poster-dotation-derogatoire', immo_autre),
            {'annee': 2026}, format='json')
        self.assertEqual(resp.status_code, 404)
