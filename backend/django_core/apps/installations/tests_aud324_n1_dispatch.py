"""AUD324 — N+1 supprimé sur les écrans planification / dispatch d'intervention.

Défaut d'origine : `InterventionSerializer` porte 5 `SerializerMethodField`
sans eager-loading — `equipe_noms` (M2M), `preparation_completion` /
`preparation_confirmee` (OneToOne inverse, jamais préchargé),
`reserves_ouvertes` (COUNT sur FK inverse), `photos_obligatoires_manquantes` →
`missing_required_shots` → `active_shotlist(company)` (la MÊME requête
`ShotListSlot` ré-exécutée par intervention, aucune mémoïsation). Et l'action
`calendrier` construisait son propre queryset SANS `prefetch_related` du tout.

Le comptage est FILTRÉ par table : une table par cause corrigée. Les requêtes
étrangères à ce correctif (dont la carte des photos, qui est par nature une
donnée PAR intervention) ne rendent donc pas ce test fragile — un cas dédié
vérifie tout de même que la carte des photos n'est plus chargée du tout quand
la société n'a aucun créneau OBLIGATOIRE.

Run :
    python manage.py test apps.installations.tests_aud324_n1_dispatch -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import localdate
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Installation, Intervention, InterventionPreparation, Reserve, ShotListSlot,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/interventions'

TABLES = {
    'shotlist': ShotListSlot._meta.db_table,
    'preparation': InterventionPreparation._meta.db_table,
    'reserve': Reserve._meta.db_table,
}


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud324-co-{n}', defaults={'nom': f'AUD324 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DispatchN1Tests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'aud324-{next(_seq)}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = auth(self.user)
        self.inst = Installation.objects.create(
            company=self.company, reference='AUD324-1',
            statut=Installation.Statut.EN_COURS)
        self.jour = str(localdate())
        ShotListSlot.objects.create(
            company=self.company, cle='avant', libelle='Avant travaux',
            phase='avant', obligatoire=True, ordre=0)

    def _creer_interventions(self, nb):
        for _ in range(nb):
            iv = Intervention.objects.create(
                company=self.company, installation=self.inst,
                type_intervention=Intervention.Type.POSE,
                statut=Intervention.Statut.PRETE,
                technicien=self.user, date_prevue=self.jour)
            iv.equipe.add(self.user)
            InterventionPreparation.objects.create(
                company=self.company, intervention=iv)
            Reserve.objects.create(
                company=self.company, intervention=iv,
                description='Reprise', statut=Reserve.Statut.OUVERTE)

    def _compte_par_table(self, url):
        with CaptureQueriesContext(connection) as ctx:
            r = self.api.get(url)
            self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        sqls = [q['sql'] for q in ctx.captured_queries]
        return {nom: sum(1 for s in sqls if table in s)
                for nom, table in TABLES.items()}

    def _assert_constant(self, url):
        self._creer_interventions(3)
        avec_3 = self._compte_par_table(url)
        self._creer_interventions(9)
        avec_12 = self._compte_par_table(url)
        self.assertEqual(avec_3, avec_12, (url, avec_3, avec_12))
        for nom, n in avec_12.items():
            self.assertLessEqual(n, 2, (url, nom, avec_12))

    def test_calendrier_compte_fixe(self):
        """ROUGE avant AUD324 : aucun prefetch, shot-list par intervention."""
        self._assert_constant(
            f'{BASE}/calendrier/?date_from={self.jour}&date_to={self.jour}')

    def test_liste_kanban_compte_fixe(self):
        self._assert_constant(f'{BASE}/')

    def test_ma_tournee_compte_fixe(self):
        self._assert_constant(f'{BASE}/ma-tournee/?date={self.jour}')

    def test_la_shotlist_est_memoisee_une_seule_fois(self):
        self._creer_interventions(6)
        comptes = self._compte_par_table(f'{BASE}/')
        self.assertEqual(comptes['shotlist'], 1, comptes)

    def test_reserves_ouvertes_reste_correct(self):
        self._creer_interventions(1)
        r = self.api.get(f'{BASE}/')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(rows[0]['reserves_ouvertes'], 1)

    def test_pas_de_carte_photos_sans_creneau_obligatoire(self):
        """Sans créneau OBLIGATOIRE, il n'y a rien à comparer : la requête
        `Attachment` par intervention devient inutile — et disparaît."""
        from apps.records.models import Attachment
        ShotListSlot.objects.filter(company=self.company).update(
            obligatoire=False)
        self._creer_interventions(4)
        with CaptureQueriesContext(connection) as ctx:
            self.api.get(f'{BASE}/')
        table = Attachment._meta.db_table
        self.assertEqual(
            sum(1 for q in ctx.captured_queries if table in q['sql']), 0)
