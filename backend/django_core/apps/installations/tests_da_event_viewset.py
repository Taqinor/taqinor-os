"""DA-EVENT-VIEWSET — l'action directe ``approuver`` (sans plan d'approbation)
émet désormais ``core.events.demande_achat_approuvee`` (NTP2P38).

``services.approuver_etape_achat`` (le chemin multi-étapes) émettait déjà cet
événement à la dernière étape — le chemin direct (``DemandeAchatViewSet.
approuver``, quand aucun plan d'approbation n'est actif) ne l'appelait pas :
un abonné (``apps.automation``, un webhook) ne voyait donc JAMAIS
l'approbation d'une réquisition sans étapes.

Run :
    python manage.py test apps.installations.tests_da_event_viewset -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'da-evt-co-{n}', defaults={'nom': f'DA Event Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company):
    return User.objects.create_user(
        username=f'da-evt-{next(_seq)}', password='x',
        role_legacy='responsable', company=company)


class DirectApprovalEmitsEventTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-EVT-1', objet='Test',
            created_by=self.user)

    def _connect(self):
        from core.events import demande_achat_approuvee
        recus = []
        # `weak=False` : ce lambda n'a AUCUNE autre référence forte (seul
        # `recus` est rendu) — avec le `weak=True` par défaut de Django il est
        # garbage-collecté dès la fin de cette ligne, le récepteur ne se
        # déclenche JAMAIS et l'espion reste vide quoi que fasse la vue (même
        # patron que core/tests/test_aud806_capture_rafraichir.py et
        # apps/ao/tests/test_statuts_ao.py).
        demande_achat_approuvee.connect(
            lambda sender, **kw: recus.append(kw),
            dispatch_uid='test_da_event_viewset', weak=False)
        return recus

    def _disconnect(self):
        from core.events import demande_achat_approuvee
        demande_achat_approuvee.disconnect(
            dispatch_uid='test_da_event_viewset')

    def test_direct_approval_emits_demande_achat_approuvee(self):
        recus = self._connect()
        try:
            self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
            r = self.api.post(
                f'{BASE}/demandes-achat/{self.da.id}/approuver/')
            self.assertEqual(r.status_code, 200, r.data)
        finally:
            self._disconnect()

        self.assertEqual(len(recus), 1)
        evt = recus[0]
        self.assertEqual(evt['demande'].pk, self.da.pk)
        self.assertEqual(evt['company'], self.company)
        self.assertEqual(evt['user'], self.user)

    def test_refus_n_emet_rien(self):
        recus = self._connect()
        try:
            self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
            r = self.api.post(
                f'{BASE}/demandes-achat/{self.da.id}/refuser/',
                {'motif_refus': 'Budget dépassé'})
            self.assertEqual(r.status_code, 200, r.data)
        finally:
            self._disconnect()

        self.assertEqual(recus, [])
