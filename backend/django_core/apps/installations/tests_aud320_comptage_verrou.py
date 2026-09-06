"""AUD320 — `SessionComptage.terminer()` prend enfin un verrou de session.

``terminer`` lisait ``session.statut`` par un ``get_object()`` simple — pas de
``select_for_update()``, pas de ``transaction.atomic()`` englobant
lecture + écriture + appel à ``appliquer_ecarts_comptage``. Ce dernier
verrouille chaque ``Produit`` mais jamais la SESSION, et ne revérifie pas son
état sous verrou : la docstring « IDEMPOTENTE » ne tenait que pour des appels
SÉQUENTIELS.

Scénario : deux POST ``/terminer/`` concurrents (double-clic, retry réseau,
deux onglets) lisent tous deux ``statut=EN_COURS`` avant que l'un ou l'autre
committe — les deux passent la garde et postent DEUX ``MouvementStock``
AJUSTEMENT pour le même écart.

NOTE D'HONNÊTETÉ : deux requêtes réellement concurrentes ne sont pas
reproductibles dans une ``TestCase`` (une seule connexion, une transaction de
test). On verrouille donc les deux choses observables et suffisantes : (1) la
requête de lecture du statut porte bien un verrou de ligne (``FOR UPDATE``) —
c'est LA correction, et sans elle la course reste ouverte ; (2) l'idempotence
séquentielle ne régresse pas.
"""
import itertools

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import ComptageLigne, SessionComptage
from apps.stock.models import MouvementStock, Produit
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


class TestVerrouSessionComptage(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud320-co-{n}', nom=f'AUD320 Co {n}')
        self.user = User.objects.create_user(
            username=f'aud320-{n}', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', prix_vente=1500,
            prix_achat=0, quantite_stock=42)
        self.session = SessionComptage.objects.create(
            company=self.company, reference=f'CYC-AUD320-{n}',
            statut=SessionComptage.Statut.EN_COURS)
        ComptageLigne.objects.create(
            session=self.session, produit=self.produit,
            quantite_theorique=42, quantite_comptee=40, compte=True)

    def _terminer(self):
        return self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/')

    def _ajustements(self):
        return MouvementStock.objects.filter(
            company=self.company, reference=self.session.reference,
            type_mouvement='ajustement')

    def test_la_lecture_du_statut_est_verrouillee(self):
        """ROUGE avant le correctif : aucun `FOR UPDATE` — la garde décidait
        sur une valeur qu'un appel concurrent pouvait déjà avoir périmée."""
        if not connection.features.has_select_for_update:  # pragma: no cover
            self.skipTest('Le moteur de base ne supporte pas SELECT FOR UPDATE.')
        table = SessionComptage._meta.db_table
        with CaptureQueriesContext(connection) as ctx:
            resp = self._terminer()
            self.assertEqual(resp.status_code, 200, resp.content)
        verrous = [q['sql'] for q in ctx.captured_queries
                   if 'FOR UPDATE' in q['sql'].upper() and table in q['sql']]
        self.assertTrue(
            verrous,
            'terminer() lit le statut de la session SANS verrou de ligne : '
            'deux appels concurrents postent deux ajustements.')

    def test_un_seul_ajustement_meme_apres_un_second_appel(self):
        self.assertEqual(self._terminer().status_code, 200)
        self.assertEqual(self._ajustements().count(), 1)
        # Second appel (double-clic / retry) : rien de plus n'est posté.
        self.assertEqual(self._terminer().status_code, 200)
        self.assertEqual(self._ajustements().count(), 1)

    def test_l_ajustement_cale_le_stock_sur_le_compte(self):
        self.assertEqual(self._terminer().status_code, 200)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 40)
        self.session.refresh_from_db()
        self.assertEqual(self.session.statut, SessionComptage.Statut.TERMINE)
