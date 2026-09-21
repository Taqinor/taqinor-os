"""WIR263 — Historique des relances de loyer PAR ÉCHÉANCE.

L'escalade 1 → 2 → 3 (le niveau 3 a une portée juridique) n'avait aucun retour
visuel : l'écran postait ``echeances-loyer/<id>/relancer/`` sans jamais relire
l'historique. Ce test AFFIRME la réponse réelle de la collection filtrée contre
l'exemple COMMITTÉ ``contract_samples/relances_loyer_par_echeance.json`` — le
même fichier que le test frontend (``BauxPage.test.jsx``) IMPORTE au lieu de
retaper sa charge utile (PACT10/PACT13).

Couvre aussi : le filtre serveur ``?echeance_loyer=`` existe déjà (aucun
filterset à ajouter), la collection est en lecture seule, et elle reste bornée
à la société de l'appelant.
"""
import json
import pathlib
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, EcheanceLoyer, Local, Locataire, Niveau, RelanceLoyer, Site,
)
from apps.immobilier.services import creer_bail, generer_echeancier

User = get_user_model()

URL = '/api/django/immobilier/relances-loyer/'

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'relances_loyer_par_echeance.json').read_text(encoding='utf-8'))


def _echeance_pour(company, suffixe):
    site = Site.objects.create(company=company, nom=f'Résidence {suffixe}')
    batiment = Batiment.objects.create(
        company=company, site=site, nom=f'Bât {suffixe}')
    niveau = Niveau.objects.create(
        company=company, batiment=batiment, numero='RDC')
    local = Local.objects.create(
        company=company, niveau=niveau, reference=f'RDC-{suffixe}')
    locataire = Locataire.objects.create(company=company, nom=f'Loc {suffixe}')
    bail = creer_bail(
        company=company, local=local, locataire=locataire,
        type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
        duree_mois=1, loyer_mensuel_ht=Decimal('3000.00'))
    generer_echeancier(bail)
    return EcheanceLoyer.objects.get(bail=bail)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir263HistoriqueRelancesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Immo WIR263', slug='immo-wir263')
        self.user = User.objects.create_user(
            username='immo-wir263-admin', password='x', company=self.company,
            role_legacy='admin')
        self.echeance = _echeance_pour(self.company, 'A')
        self.autre_echeance = _echeance_pour(self.company, 'B')
        self.api = auth(self.user)

    def _relancer(self, echeance, canal):
        resp = self.api.post(
            f'/api/django/immobilier/echeances-loyer/{echeance.id}/relancer/',
            {'canal': canal}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data

    def test_deux_relances_deux_lignes_niveau_2_puis_1(self):
        """Le cœur de WIR263 : 2 relances ⇒ 2 lignes, niveau atteint = 2."""
        self._relancer(self.echeance, RelanceLoyer.Canal.WHATSAPP)
        self._relancer(self.echeance, RelanceLoyer.Canal.EMAIL)

        resp = self.api.get(URL, {'echeance_loyer': self.echeance.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = resp.data['results']
        self.assertEqual(len(lignes), 2)
        # Ordre serveur ['-date_envoi', '-id'] : le niveau le plus haut d'abord.
        self.assertEqual([row['niveau'] for row in lignes], [2, 1])
        self.assertEqual(max(row['niveau'] for row in lignes), 2)

    def test_la_reponse_a_la_forme_du_contrat_committe(self):
        """La réponse RÉELLE porte exactement les clés de l'exemple committé."""
        self._relancer(self.echeance, RelanceLoyer.Canal.WHATSAPP)
        self._relancer(self.echeance, RelanceLoyer.Canal.EMAIL)

        resp = self.api.get(URL, {'echeance_loyer': self.echeance.id})
        self.assertEqual(
            set(resp.data), set(CONTRAT['exemple_page']),
            "l'enveloppe de pagination diverge du contrat committé")
        attendu = set(CONTRAT['exemple'])
        for ligne in resp.data['results']:
            self.assertEqual(
                set(ligne), attendu,
                'une ligne de relance diverge du contrat committé')
        # Vocabulaire : le canal et son libellé viennent bien du serveur.
        recente = resp.data['results'][0]
        self.assertEqual(recente['canal'], CONTRAT['exemple']['canal'])
        self.assertEqual(
            recente['canal_display'], CONTRAT['exemple']['canal_display'])
        self.assertEqual(recente['niveau'], CONTRAT['exemple']['niveau'])
        ancienne = resp.data['results'][1]
        self.assertEqual(
            ancienne['canal'], CONTRAT['exemple_niveau_1']['canal'])
        self.assertEqual(
            ancienne['canal_display'],
            CONTRAT['exemple_niveau_1']['canal_display'])
        self.assertEqual(
            ancienne['niveau'], CONTRAT['exemple_niveau_1']['niveau'])

    def test_le_filtre_par_echeance_existe_deja_cote_serveur(self):
        """``?echeance_loyer=`` borne bien la liste (aucun filterset à ajouter)."""
        self._relancer(self.echeance, RelanceLoyer.Canal.WHATSAPP)
        self._relancer(self.autre_echeance, RelanceLoyer.Canal.COURRIER)

        resp = self.api.get(URL, {'echeance_loyer': self.echeance.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(
            resp.data['results'][0]['echeance_loyer'], self.echeance.id)

    def test_collection_en_lecture_seule(self):
        """Une relance naît TOUJOURS de ``relancer/`` — jamais d'un POST direct."""
        resp = self.api.post(
            URL, {'echeance_loyer': self.echeance.id}, format='json')
        self.assertEqual(resp.status_code, 405, resp.data)

    def test_bornee_a_la_societe_de_l_appelant(self):
        autre_company = Company.objects.create(
            nom='Immo WIR263 bis', slug='immo-wir263-bis')
        autre_user = User.objects.create_user(
            username='immo-wir263-admin-bis', password='x',
            company=autre_company, role_legacy='admin')
        echeance_tierce = _echeance_pour(autre_company, 'C')
        RelanceLoyer.objects.create(
            company=autre_company, echeance_loyer=echeance_tierce, niveau=1)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['results'], [])
        # L'autre société voit la sienne, et seulement la sienne.
        resp_bis = auth(autre_user).get(URL)
        self.assertEqual(len(resp_bis.data['results']), 1)
        self.assertEqual(
            resp_bis.data['results'][0]['echeance_loyer'], echeance_tierce.id)
