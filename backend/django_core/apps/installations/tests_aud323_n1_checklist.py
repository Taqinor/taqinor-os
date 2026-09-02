"""AUD323 — la liste des chantiers ne charge plus la checklist chantier par chantier.

Défaut d'origine : `InstallationSerializer.get_checklist_completion` exécute
`obj.checklist.all()` PAR instance, et le queryset d'`InstallationViewSet`
préchargeait `interventions__*` / `equipements` mais PAS `'checklist'`
(`ChantierChecklistItem`, `related_name='checklist'`). Une société avec 300
chantiers actifs payait 300 requêtes SQL supplémentaires sur l'écran
liste/planification, la latence croissant linéairement avec le portefeuille.

Le comptage est FILTRÉ sur la table de la checklist : les autres requêtes de
la page (dont les N+1 du serializer d'intervention imbriqué) relèvent
d'AUD324 et ne doivent pas rendre ce test fragile.

Run :
    python manage.py test apps.installations.tests_aud323_n1_checklist -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import ChantierChecklistItem, Installation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'
TABLE = ChantierChecklistItem._meta.db_table


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud323-co-{n}', defaults={'nom': f'AUD323 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ChecklistPrefetchTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'aud323-resp-{next(_seq)}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = auth(self.user)

    def _creer_chantiers(self, nb):
        for _ in range(nb):
            inst = Installation.objects.create(
                company=self.company, reference=f'AUD323-{next(_seq)}',
                statut=Installation.Statut.PLANIFIE)
            for k in range(2):
                ChantierChecklistItem.objects.create(
                    company=self.company, installation=inst,
                    cle=f'etape-{k}', libelle=f'Étape {k}', ordre=k,
                    fait=(k == 0))

    def _requetes_checklist(self):
        with CaptureQueriesContext(connection) as ctx:
            r = self.api.get(f'{BASE}/')
            self.assertEqual(r.status_code, 200)
        return [q['sql'] for q in ctx.captured_queries if TABLE in q['sql']]

    def test_le_nombre_de_requetes_checklist_ne_croit_pas_avec_n(self):
        """ROUGE avant AUD323 : 3 requêtes pour 3 chantiers, 10 pour 10."""
        self._creer_chantiers(3)
        avec_3 = len(self._requetes_checklist())
        self._creer_chantiers(7)
        avec_10 = len(self._requetes_checklist())
        self.assertEqual(avec_3, avec_10)
        # Une seule requête de préchargement, quel que soit le portefeuille.
        self.assertEqual(avec_10, 1)

    def test_la_completion_reste_correcte(self):
        self._creer_chantiers(1)
        r = self.api.get(f'{BASE}/')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(rows[0]['checklist_completion'], 50)
