"""AOF1 — le CORPS des 8 ViewSets AO et des 2 services AO vit dans ``apps.ao``.

Jusqu'ici ``apps/ao/views.py`` et ``apps/ao/services.py`` n'étaient que des
ré-exports : les classes vivaient dans ``apps.compta.views`` (adossées à
``_ComptaBaseViewSet``) et les fonctions dans ``apps.compta.services``. AOF1
inverse le shim : le corps est dans ``ao``, ``compta`` ré-exporte.

Ces tests verrouillent les trois promesses :
  1. aucune classe/fonction AO n'est DÉFINIE dans ``compta`` (``__module__``) ;
  2. le shim inverse ré-exporte les MÊMES objets (aucun doublon de classe) ;
  3. les DEUX jeux de routes (``/api/django/ao/…`` et
     ``/api/django/compta/…``) répondent à l'identique et restent scopés
     société.

Run :
    python manage.py test apps.ao.tests.test_relogement_viewsets -v2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()

VIEWSET_NAMES = [
    'AppelOffreViewSet',
    'BordereauPrixViewSet',
    'LigneBordereauViewSet',
    'CautionSoumissionViewSet',
    'DossierSoumissionViewSet',
    'PieceSoumissionViewSet',
    'EcheanceAOViewSet',
    'ResultatAOViewSet',
]

SERVICE_NAMES = ['echeances_ao_dues', 'taux_reussite_ao']


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


def rows_of(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class TestAOF1CorpsRelogeDansAo(SimpleTestCase):
    """Les 8 ViewSets + 2 services sont DÉFINIS dans ``apps.ao``."""

    def test_viewsets_definis_dans_apps_ao_views(self):
        from apps.ao import views as ao_views
        for name in VIEWSET_NAMES:
            cls = getattr(ao_views, name)
            self.assertEqual(
                cls.__module__, 'apps.ao.views',
                f"{name} doit être DÉFINI dans apps.ao.views (trouvé : "
                f"{cls.__module__}).")

    def test_services_definis_dans_apps_ao_services(self):
        from apps.ao import services as ao_services
        for name in SERVICE_NAMES:
            fn = getattr(ao_services, name)
            self.assertEqual(
                fn.__module__, 'apps.ao.services',
                f"{name} doit être DÉFINI dans apps.ao.services (trouvé : "
                f"{fn.__module__}).")

    def test_shim_compta_reexporte_les_memes_objets(self):
        """Le shim INVERSE ne DUPLIQUE rien : mêmes objets, pas des copies."""
        from apps.ao import services as ao_services, views as ao_views
        from apps.compta import services as compta_services
        from apps.compta import views as compta_views
        for name in VIEWSET_NAMES:
            self.assertIs(getattr(compta_views, name),
                          getattr(ao_views, name), name)
        for name in SERVICE_NAMES:
            self.assertIs(getattr(compta_services, name),
                          getattr(ao_services, name), name)

    def test_socle_scope_societe_conserve(self):
        """La base AO reste scopée société (TenantMixin dans le MRO)."""
        from apps.ao import views as ao_views
        for name in VIEWSET_NAMES:
            cls = getattr(ao_views, name)
            mro_names = {base.__name__ for base in cls.__mro__}
            self.assertIn('TenantMixin', mro_names, name)


class TestAOF1RoutesIdentiques(TestCase):
    """Les deux jeux de routes répondent à l'identique (non-régression)."""

    def setUp(self):
        self.company = make_company('aof1-co', 'AOF1 Co')
        self.user = make_user(self.company, 'aof1_resp')
        self.api = auth(self.user)

    def _creer_ao(self, reference, objet='Centrale PV'):
        from apps.ao.models import AppelOffre
        return AppelOffre.objects.create(
            company=self.company, reference=reference, objet=objet)

    def test_servie_sous_le_seul_prefixe_canonique(self):
        """PACT26 — fin du double montage : /ao/ sert, /compta/ ne sert plus.

        Ce test pinait auparavant l'ÉGALITÉ des deux préfixes (garantie de
        transition du découpage ODX11). PACT26 met fin à cette transition : le
        double montage faussait tout comptage automatique et forçait chaque
        écran à choisir arbitrairement entre deux URLs pour la même donnée.
        L'invariant utile est désormais l'UNICITÉ du préfixe.
        """
        ao = self._creer_ao('AO-AOF1-01')
        r_ao = self.api.get('/api/django/ao/appels-offres/')
        self.assertEqual(r_ao.status_code, 200, r_ao.data)
        self.assertIn(ao.id, [x['id'] for x in rows_of(r_ao)])
        r_compta = self.api.get('/api/django/compta/appels-offres/')
        self.assertEqual(r_compta.status_code, 404)

    def test_creation_force_la_societe_cote_serveur(self):
        r = self.api.post('/api/django/ao/appels-offres/', {
            'reference': 'AO-AOF1-02', 'objet': 'Pompage',
            'type_marche': 'public',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        from apps.ao.models import AppelOffre
        self.assertEqual(
            AppelOffre.objects.get(id=r.data['id']).company_id,
            self.company.id)

    def test_isolation_multi_societe_sur_le_prefixe_canonique(self):
        autre = make_company('aof1-autre', 'Autre Co')
        from apps.ao.models import AppelOffre
        AppelOffre.objects.create(
            company=autre, reference='AO-AOF1-X', objet='Autre société')
        r = self.api.get('/api/django/ao/appels-offres/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(rows_of(r), [])

    def test_actions_metier_conservees(self):
        """``dues`` (échéancier) et ``stats`` (taux de réussite) répondent."""
        for url in ('/api/django/ao/echeances-ao/dues/',):
            r = self.api.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertEqual(r.data, [], url)
        for url in ('/api/django/ao/resultats-ao/stats/',):
            r = self.api.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertEqual(r.data['total_decides'], 0, url)
