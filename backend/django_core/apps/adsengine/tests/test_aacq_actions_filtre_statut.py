"""AACQ61 — ``GET /api/django/adsengine/actions/?statut=`` filtre côté serveur.

``proposee``, ``approuvee``, liste à virgules ; alias ``en_attente`` =
proposee+approuvee ; valeur inconnue → 400 « Statut inconnu : <valeur> ». Sans
paramètre, la liste (Journal d'actions, PUB40) est inchangée. Chaque ligne a la
forme du contrat ``contract_samples/engine_action.json`` (AACQ60).
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import EngineAction

User = get_user_model()
BASE = '/api/django/adsengine/actions/'
CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'engine_action.json')


def _ids(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data \
        else data
    return [r['id'] for r in rows]


def _count(resp):
    data = resp.data
    return data['count'] if isinstance(data, dict) and 'count' in data \
        else len(data)


class FiltreStatutTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AACQ61', slug='aacq61')
        role = Role.objects.create(
            company=self.company, nom='aacq61-admin',
            permissions=['adsengine_view', 'adsengine_manage',
                         'adsengine_approve'])
        user = User.objects.create_user(
            username='aacq61-admin', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        statuts = [EngineAction.Statut.APPLIQUEE, EngineAction.Statut.REJETEE]
        for i in range(60):
            EngineAction.objects.create(
                company=self.company, kind=EngineAction.Kind.PAUSE,
                payload={'campaign_id': f'c{i}'}, reason_fr='Récente.',
                status=statuts[i % 2])
        self.proposee = EngineAction.objects.create(
            company=self.company, kind='rebalance_adset_budget',
            payload={'adset_id': 'PRB_A1', 'daily_budget': 10000,
                     'current_budget': 20000, 'new_daily_budget_mad': 100.0,
                     'target_daily_budget_mad': 230.0},
            reason_fr='Ancienne proposition.',
            status=EngineAction.Statut.PROPOSEE)
        EngineAction.objects.filter(pk=self.proposee.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=30))

    def test_en_attente_exclut_rejetees_et_appliquees(self):
        approuvee = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.PAUSE,
            payload={'campaign_id': 'cx'}, reason_fr='Approuvée.',
            status=EngineAction.Statut.APPROUVEE)
        resp = self.api.get(BASE, {'statut': 'en_attente'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(sorted(_ids(resp)),
                         sorted([self.proposee.pk, approuvee.pk]))
        self.assertEqual(_count(resp), 2)
        resp = self.api.get(BASE, {'statut': 'proposee'})
        self.assertEqual(_ids(resp), [self.proposee.pk])
        self.assertEqual(_count(resp), 1)
        resp = self.api.get(BASE, {'statut': 'proposee,approuvee'})
        self.assertEqual(_count(resp), 2)
        # Lecture seule : relire ⇒ mêmes ids, aucune ligne écrite.
        avant = EngineAction.objects.count()
        resp2 = self.api.get(BASE, {'statut': 'proposee'})
        self.assertEqual(_ids(resp2), [self.proposee.pk])
        self.assertEqual(EngineAction.objects.count(), avant)

    def test_forme_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        resp = self.api.get(BASE, {'statut': 'en_attente'})
        rows = resp.data['results'] if 'results' in resp.data else resp.data
        ligne = dict(rows[0])
        self.assertEqual(set(ligne), set(contrat['exemple']))
        self.assertEqual(set(ligne['payload']),
                         set(contrat['exemple']['payload']))
        self.assertNotIn('budget_avant', ligne['payload'])

    def test_statut_inconnu_400(self):
        resp = self.api.get(BASE, {'statut': 'xyz'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(str(resp.data['detail']), 'Statut inconnu : xyz')
        resp = self.api.get(BASE, {'statut': 'proposee,xyz'})
        self.assertEqual(resp.status_code, 400)

    def test_sans_parametre_inchange(self):
        resp = self.api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(_count(resp), 61)
        aujourd_hui = timezone.localdate().isoformat()
        resp = self.api.get(BASE, {'debut': aujourd_hui, 'fin': aujourd_hui})
        self.assertEqual(_count(resp), 60)
        self.assertNotIn(self.proposee.pk, _ids(resp))
