"""WIR86 — décision « Programme/Projet multi-chantiers : consolider ».

Décision (2026-07-18, tracée dans ``docs/module-map.md``) : le système Projet
CANONIQUE est ``apps/gestion_projet`` (39 modèles, seul câblé côté frontend).
La famille Programme/Projet d'``installations`` (FG291-301) n'est PAS
supprimée — elle est GELÉE et DÉPRÉCIÉE : elle continue de servir ses données
à l'identique, mais chaque réponse porte l'entête RFC 8594 ``Deprecation`` +
un lien ``successor-version`` vers l'API canonique.

Ces tests verrouillent exactement ça :
  * les 7 familles d'endpoints ``programme*`` portent la marque de dépréciation ;
  * la marque est bien SCOPÉE (un endpoint installations hors-programme ne la
    porte pas) ;
  * le comportement métier est INCHANGÉ (création toujours 201, société et
    référence posées côté serveur, isolation société intacte) — la décision
    reste donc entièrement réversible.

Run :
    python manage.py test apps.installations.tests_wir86_programme_deprecie -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Projet
from apps.installations.views.program import PROGRAMME_SUCCESSOR_URL

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'

# Les 7 familles d'endpoints figées par WIR86 (FG291-301).
PROGRAMME_ROUTES = [
    'programmes',
    'programme-taches',
    'programme-chantiers',
    'programme-devis',
    'programme-tickets',
    'programme-budgets',
    'programme-engagements',
]


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'wir86-co-{n}'
    nom = nom or f'WIR86 Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestWir86ProgrammeDeprecie(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'wir86-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)

    def _assert_deprecated(self, response):
        self.assertEqual(response['Deprecation'], 'true')
        self.assertIn('rel="successor-version"', response['Link'])
        self.assertIn(PROGRAMME_SUCCESSOR_URL, response['Link'])

    def test_les_7_familles_programme_portent_la_marque_de_depreciation(self):
        """WIR86 — chaque endpoint `programme*` annonce sa dépréciation et
        pointe vers le système Projet canonique (`gestion_projet`)."""
        for route in PROGRAMME_ROUTES:
            with self.subTest(route=route):
                r = self.api.get(f'{BASE}/{route}/')
                self.assertEqual(r.status_code, 200, r.data)
                self._assert_deprecated(r)

    def test_successeur_pointe_vers_gestion_projet(self):
        """WIR86 — le successeur déclaré est bien l'API `gestion_projet`, pas
        une autre surface `installations`."""
        self.assertIn('gestion-projet', PROGRAMME_SUCCESSOR_URL)

    def test_marque_scopee_aux_endpoints_programme(self):
        """WIR86 — le reste d'`installations` n'est PAS déprécié : la marque ne
        doit pas fuiter sur les chantiers/interventions."""
        from apps.installations.views.installation import InstallationViewSet
        from apps.installations.views.intervention import InterventionViewSet
        from apps.installations.views.program import (
            DeprecatedProgrammeSurfaceMixin, ProjetViewSet, ProjetTacheViewSet,
            ProjetChantierViewSet, ProjetDevisViewSet, ProjetTicketViewSet,
            BudgetProjetViewSet, BudgetEngagementViewSet,
        )
        for vs in [ProjetViewSet, ProjetTacheViewSet, ProjetChantierViewSet,
                   ProjetDevisViewSet, ProjetTicketViewSet,
                   BudgetProjetViewSet, BudgetEngagementViewSet]:
            with self.subTest(viewset=vs.__name__):
                self.assertTrue(
                    issubclass(vs, DeprecatedProgrammeSurfaceMixin))
        for vs in [InstallationViewSet, InterventionViewSet]:
            with self.subTest(viewset=vs.__name__):
                self.assertFalse(
                    issubclass(vs, DeprecatedProgrammeSurfaceMixin))

    def test_comportement_metier_inchange_creation(self):
        """WIR86 — surface GELÉE, pas cassée : la création d'un programme
        répond toujours 201, avec société + référence posées côté serveur, et
        porte la marque de dépréciation."""
        r = self.api.post(f'{BASE}/programmes/', {
            'nom': 'Ferme 4 forages',
            'reference': 'HACK-1',   # read-only, ignoré
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self._assert_deprecated(r)
        projet = Projet.objects.get(id=r.data['id'])
        self.assertEqual(projet.company_id, self.company.id)
        self.assertTrue(projet.reference.startswith('PRG-'))
        self.assertNotEqual(projet.reference, 'HACK-1')

    def test_isolation_societe_intacte(self):
        """WIR86 — la dépréciation ne touche ni le scope société ni les
        permissions : la société B ne voit toujours pas les programmes de A."""
        Projet.objects.create(
            company=self.company, reference='PRG-WIR86-1', nom='Secret A')
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'wir86b-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/programmes/')
        self.assertEqual(r.status_code, 200)
        results = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(
            [p for p in results if p['reference'] == 'PRG-WIR86-1'], [])
        self._assert_deprecated(r)
