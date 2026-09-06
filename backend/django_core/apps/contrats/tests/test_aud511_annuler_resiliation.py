"""AUD511 — une résiliation faite par erreur devient rattrapable.

``Resiliation`` déclarait TROIS statuts (``demande``/``effective``/``annulee``)
mais seul ``resilier_contrat`` en créait — toujours en ``demande``. Aucun
service, aucune vue (``ResiliationViewSet`` est en lecture seule), aucun admin
n'écrivait ``annulee`` ni ``effective`` : c'étaient des ÉTATS MORTS. Et
``Contrat.statut = RESILIE`` était TERMINAL dans la machine d'états — donc même
une résiliation annulée n'aurait JAMAIS rendu son contrat ACTIF.

Décision fondateur : câbler une VRAIE annulation (besoin métier réel), pas
retirer les états. Fenêtre : avant la date d'effet — au-delà, la résiliation a
produit ses conséquences.
"""
import itertools
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.contrats import services
from apps.contrats.models import Contrat, PartieContrat, Resiliation
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/contrats/contrats'


class TestAnnulerResiliation(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud511-{n}', nom=f'AUD511 Co {n}')
        self.user = User.objects.create_user(
            username=f'aud511-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.contrat = Contrat.objects.create(
            company=self.company, created_by=self.user,
            reference=f'CTR-AUD511-{n}', objet='Maintenance',
            statut=Contrat.Statut.ACTIF, montant=Decimal('12000'))
        for i in range(2):
            PartieContrat.objects.create(
                company=self.company, contrat=self.contrat,
                nom=f'Partie {i}', ordre=i)

    def _resilier(self, jours=30):
        return self.api.post(
            f'{BASE}/{self.contrat.id}/resilier/',
            {'motif': 'Erreur de saisie',
             'date_effet': (timezone.localdate()
                            + timedelta(days=jours)).isoformat()},
            format='json')

    def _annuler(self):
        return self.api.post(
            f'{BASE}/{self.contrat.id}/annuler-resiliation/',
            {'motif': 'Résiliation saisie par erreur'}, format='json')

    def test_dans_la_fenetre_le_contrat_redevient_actif(self):
        """ROUGE avant le correctif : AUCUNE route ne permettait d'annuler."""
        self.assertEqual(self._resilier().status_code, 201)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, Contrat.Statut.RESILIE)

        resp = self._annuler()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], Resiliation.Statut.ANNULEE)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, Contrat.Statut.ACTIF)

    def test_hors_fenetre_l_annulation_est_refusee(self):
        """Date d'effet atteinte : la résiliation a produit ses conséquences."""
        self.assertEqual(self._resilier(jours=0).status_code, 201)
        resp = self._annuler()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, Contrat.Statut.RESILIE)
        resiliation = Resiliation.objects.get(contrat=self.contrat)
        self.assertEqual(resiliation.statut, Resiliation.Statut.DEMANDE)

    def test_sans_resiliation_l_action_est_refusee(self):
        resp = self._annuler()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('aucune résiliation', resp.data['detail'].lower())

    def test_le_service_leve_une_erreur_typee(self):
        with self.assertRaises(services.AnnulationResiliationError):
            services.annuler_resiliation(self.contrat)

    # ── L'arête est RÉSERVÉE à cette action ──────────────────────────────

    def test_la_porte_generique_refuse_de_reactiver_un_contrat_resilie(self):
        """L'arête `RESILIE → ACTIF` existe pour la SEULE action dédiée : la
        porte générique la refuse, sinon le contrat redeviendrait actif en
        laissant sa résiliation vivante."""
        self.assertEqual(self._resilier().status_code, 201)
        resp = self.api.post(
            f'{BASE}/{self.contrat.id}/changer-statut/',
            {'statut': 'actif'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('annuler-resiliation', resp.data['detail'])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, Contrat.Statut.RESILIE)
        resiliation = Resiliation.objects.get(contrat=self.contrat)
        self.assertEqual(resiliation.statut, Resiliation.Statut.DEMANDE)

    def test_une_seconde_resiliation_redevient_possible_apres_annulation(self):
        """L'annulation libère bien la garde d'unicité de `resiliation_active`
        (elle exclut les ANNULEE)."""
        self.assertEqual(self._resilier().status_code, 201)
        self.assertEqual(self._annuler().status_code, 200)
        self.assertEqual(self._resilier().status_code, 201)
        self.assertEqual(
            Resiliation.objects.filter(contrat=self.contrat).count(), 2)
