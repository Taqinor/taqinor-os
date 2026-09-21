"""Tests QHSE12 — Relances CAPA en retard (notifications / digest).

Couvre :

* le sélecteur ``capa_en_retard`` ne retient que les CAPA échues ET ouvertes
  (à faire / en cours), exclut celles réalisées/vérifiées, sans échéance, ou
  encore dans les temps ; scopé société ;
* le service ``relancer_capa_en_retard`` notifie chaque responsable (in-app) et
  renvoie un digest cohérent (total / notifiées / sans responsable) ;
* les endpoints ``…/capa/en-retard/`` (liste) et ``…/capa/relancer-retards/``
  (digest) restent scopés société et réservés au palier Responsable/Admin.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.notifications.models import Notification
from apps.qhse.models import ActionCorrectivePreventive, NonConformite
from apps.qhse.selectors import capa_en_retard
from apps.qhse.services import relancer_capa_en_retard

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_capa(company, echeance, statut, responsable=None):
    ncr = NonConformite.objects.create(company=company, titre='NCR')
    return ActionCorrectivePreventive.objects.create(
        company=company, non_conformite=ncr, description='Reprise',
        echeance=echeance, statut=statut, responsable=responsable)


class CapaEnRetardSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse12-sel', 'Sel')
        self.today = timezone.localdate()
        self.hier = self.today - timedelta(days=3)
        self.demain = self.today + timedelta(days=3)

    def test_only_overdue_open(self):
        S = ActionCorrectivePreventive.Statut
        en_retard = make_capa(self.co, self.hier, S.A_FAIRE)
        make_capa(self.co, self.hier, S.REALISEE)        # résolue → exclue
        make_capa(self.co, self.hier, S.VERIFIEE)        # vérifiée → exclue
        make_capa(self.co, self.demain, S.A_FAIRE)       # pas échue → exclue
        make_capa(self.co, None, S.EN_COURS)             # sans échéance → exclue
        ids = list(capa_en_retard(self.co).values_list('id', flat=True))
        self.assertEqual(ids, [en_retard.id])

    def test_company_scoped(self):
        S = ActionCorrectivePreventive.Statut
        make_capa(self.co, self.hier, S.A_FAIRE)
        other = make_company('qhse12-sel-b', 'B')
        make_capa(other, self.hier, S.A_FAIRE)
        self.assertEqual(capa_en_retard(other).count(), 1)
        self.assertEqual(capa_en_retard(self.co).count(), 1)


class CapaRelanceServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse12-svc', 'Svc')
        self.resp = make_user(self.co, 'qhse12-resp')
        self.today = timezone.localdate()
        self.hier = self.today - timedelta(days=5)

    def test_digest_and_notification(self):
        S = ActionCorrectivePreventive.Statut
        make_capa(self.co, self.hier, S.A_FAIRE, responsable=self.resp)
        make_capa(self.co, self.hier, S.EN_COURS)  # sans responsable
        digest = relancer_capa_en_retard(self.co)
        self.assertEqual(digest['total'], 2)
        self.assertEqual(digest['notifiees'], 1)
        self.assertEqual(digest['sans_responsable'], 1)
        self.assertEqual(len(digest['items']), 2)
        self.assertEqual(digest['items'][0]['jours_retard'], 5)
        # Une notification in-app a bien été créée pour le responsable.
        self.assertEqual(
            Notification.objects.filter(recipient=self.resp).count(), 1)

    def test_no_overdue_empty_digest(self):
        digest = relancer_capa_en_retard(self.co)
        self.assertEqual(digest['total'], 0)
        self.assertEqual(digest['items'], [])


class CapaRelanceApiTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse12-api', 'Api')
        self.user = make_user(self.co, 'qhse12-api')
        self.today = timezone.localdate()
        self.hier = self.today - timedelta(days=2)
        make_capa(self.co, self.hier,
                  ActionCorrectivePreventive.Statut.A_FAIRE,
                  responsable=self.user)

    def test_en_retard_list(self):
        resp = auth(self.user).get('/api/django/qhse/capa/en-retard/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)

    def test_relancer_retards_digest(self):
        resp = auth(self.user).post(
            '/api/django/qhse/capa/relancer-retards/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['notifiees'], 1)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse12-normal', role='normal')
        resp = auth(normal).get('/api/django/qhse/capa/en-retard/')
        self.assertEqual(resp.status_code, 403)
