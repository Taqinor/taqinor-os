"""WIR263 — l'historique des relances de loyer est LISIBLE par l'écran.

L'escalade niveau 1 → 2 → 3 existait côté serveur (NTPRO8) mais l'écran des
baux n'avait AUCUN retour visuel : on relançait à l'aveugle, alors que le
niveau 3 a une portée juridique (mise en demeure).

Ce test AFFIRME l'exemple committé dans
``apps/immobilier/contract_samples/relance_loyer.json`` — le MÊME fichier que
le test frontend importe (PACT10/PACT13, jamais un mock écrit à la main). Si
le sérialiseur change de forme, ce test rougit ici ET côté frontend.

Run :
    docker compose exec django_core python manage.py test \
        apps.immobilier.tests.test_wir263_historique_relances -v 2
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
from apps.immobilier.models import (
    Bail, Batiment, Local, Locataire, Niveau, RelanceLoyer, Site,
)
from apps.immobilier.services import (
    creer_bail, generer_echeancier, relancer_echeance,
)

User = get_user_model()

RELANCES = '/api/django/immobilier/relances-loyer/'
ECHANTILLON = (
    Path(__file__).resolve().parents[1]
    / 'contract_samples' / 'relance_loyer.json'
)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir263HistoriqueRelancesTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='wir263-co', defaults={'nom': 'WIR263 Co'})
        self.autre, _ = Company.objects.get_or_create(
            slug='wir263-autre', defaults={'nom': 'WIR263 Autre'})
        self.user = User.objects.create_user(
            username='wir263_admin', password='x', company=self.company,
            role_legacy='admin')
        self.user_autre = User.objects.create_user(
            username='wir263_autre', password='x', company=self.autre,
            role_legacy='admin')
        self.api = _auth(self.user)
        self.api_autre = _auth(self.user_autre)

        site = Site.objects.create(company=self.company, nom='Résidence')
        batiment = Batiment.objects.create(
            company=self.company, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.company, batiment=batiment, numero='RDC')
        local = Local.objects.create(
            company=self.company, niveau=niveau, reference='RDC-01')
        locataire = Locataire.objects.create(
            company=self.company, nom='Bennani')
        self.bail = creer_bail(
            company=self.company, local=local, locataire=locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=1, loyer_mensuel_ht=Decimal('3000.00'))
        generer_echeancier(self.bail)
        self.echeance = self.bail.echeances.first()

    # ── Le contrat committé EST la forme réellement servie ───────────────
    def test_lexemple_committe_correspond_au_serialiseur(self):
        document = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        relancer_echeance(self.echeance, canal=RelanceLoyer.Canal.WHATSAPP,
                          template_utilise='relance_n1')
        resp = self.api.get(RELANCES, {'echeance_loyer': self.echeance.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = (resp.data['results']
                if isinstance(resp.data, dict) else resp.data)
        self.assertEqual(set(rows[0]), set(document['exemple']))
        # Chaque variante publie les MÊMES clés (un autre ÉTAT, jamais une
        # autre FORME).
        for cle, exemple in document.items():
            if cle.startswith('exemple'):
                self.assertEqual(set(exemple), set(document['exemple']), cle)

    # ── L'escalade est lisible ───────────────────────────────────────────
    def test_deux_relances_donnent_deux_lignes_de_niveaux_1_puis_2(self):
        relancer_echeance(self.echeance, canal=RelanceLoyer.Canal.EMAIL)
        relancer_echeance(self.echeance, canal=RelanceLoyer.Canal.WHATSAPP)
        resp = self.api.get(RELANCES, {'echeance_loyer': self.echeance.id})
        rows = (resp.data['results']
                if isinstance(resp.data, dict) else resp.data)
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(r['niveau'] for r in rows), [1, 2])

    def test_le_niveau_est_plafonne_a_3(self):
        for _ in range(5):
            relancer_echeance(self.echeance)
        resp = self.api.get(RELANCES, {'echeance_loyer': self.echeance.id})
        rows = (resp.data['results']
                if isinstance(resp.data, dict) else resp.data)
        self.assertEqual(max(r['niveau'] for r in rows), 3)

    # ── Le filtre existe ET scope la société ─────────────────────────────
    def test_filtre_par_echeance_et_isolation_societe(self):
        relancer_echeance(self.echeance)
        autre_echeance = self.bail.echeances.exclude(
            pk=self.echeance.pk).first()
        if autre_echeance is not None:
            resp = self.api.get(
                RELANCES, {'echeance_loyer': autre_echeance.id})
            rows = (resp.data['results']
                    if isinstance(resp.data, dict) else resp.data)
            self.assertEqual(len(rows), 0)

        vue_autre = self.api_autre.get(
            RELANCES, {'echeance_loyer': self.echeance.id})
        rows_autre = (vue_autre.data['results']
                      if isinstance(vue_autre.data, dict) else vue_autre.data)
        self.assertEqual(len(rows_autre), 0)

    def test_relance_en_lecture_seule_via_lapi(self):
        resp = self.api.post(RELANCES, {
            'echeance_loyer': self.echeance.id, 'canal': 'email',
        }, format='json')
        self.assertIn(resp.status_code, (403, 405))
