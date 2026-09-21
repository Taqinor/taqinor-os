"""XMKT35 — Posts réseaux sociaux : planification, rappel gated, calendrier.

Couvre : planifier un post (brouillon → planifié) ; à l'échéance SANS jeton
Meta Graph → rappel manuel notifié UNE fois (texte prêt à coller, post reste
planifié, aucun appel réseau) ; AVEC jeton (mock) → publication effective
(statut publié + external_id), échec API → statut échec ; le calendrier
marketing (XMKT30 partiel) affiche le post ; multi-tenant.
"""
import io
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, PostSocial
from apps.notifications.models import EventType, Notification

User = get_user_model()

META_ENV = {
    'META_GRAPH_ENABLED': '1',
    'META_GRAPH_TOKEN': 'fake-token',
    'META_GRAPH_PAGE_ID': '123456',
}


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


class PlanifierPostSocialTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt35-plan', 'XMKT35 Plan')
        self.user = make_user(self.co, 'xmkt35-plan-user')

    def test_planifier_brouillon_devient_planifie(self):
        post = PostSocial.objects.create(
            company=self.co, texte='Nouveau chantier livré à Rabat',
            created_by=self.user)
        quand = timezone.now() + timezone.timedelta(days=1)
        services.planifier_post_social(post, date_planifiee=quand)
        post.refresh_from_db()
        self.assertEqual(post.statut, PostSocial.Statut.PLANIFIE)
        self.assertEqual(post.date_planifiee, quand)

    def test_post_publie_jamais_replanifie(self):
        post = PostSocial.objects.create(
            company=self.co, texte='x', statut=PostSocial.Statut.PUBLIE,
            created_by=self.user)
        services.planifier_post_social(
            post, date_planifiee=timezone.now())
        post.refresh_from_db()
        self.assertEqual(post.statut, PostSocial.Statut.PUBLIE)

    def test_endpoint_planifier(self):
        post = PostSocial.objects.create(
            company=self.co, texte='y', created_by=self.user)
        api = auth(self.user)
        quand = (timezone.now() + timezone.timedelta(hours=3)).isoformat()
        resp = api.post(
            f'/api/django/compta/posts-sociaux/{post.id}/planifier/',
            {'date_planifiee': quand}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        post.refresh_from_db()
        self.assertEqual(post.statut, PostSocial.Statut.PLANIFIE)


class RappelManuelSansCleTests(TestCase):
    """Sans jeton Meta Graph : rappel notifié une fois, aucun appel réseau."""

    def setUp(self):
        self.co = make_company('xmkt35-rappel', 'XMKT35 Rappel')
        self.user = make_user(self.co, 'xmkt35-rappel-user')
        self.post = PostSocial.objects.create(
            company=self.co, texte='Promo panneaux — texte prêt à coller',
            statut=PostSocial.Statut.PLANIFIE,
            date_planifiee=timezone.now() - timezone.timedelta(minutes=5),
            created_by=self.user)

    def test_rappel_notifie_une_fois_a_echeance(self):
        with mock.patch('urllib.request.urlopen') as m_urlopen:
            traites = services.traiter_posts_sociaux_dus(self.co)
            m_urlopen.assert_not_called()
        self.assertEqual(len(traites), 1)
        notes = Notification.objects.filter(
            company=self.co, recipient=self.user,
            event_type=EventType.POST_SOCIAL_RAPPEL)
        self.assertEqual(notes.count(), 1)
        # Le texte prêt à coller est dans le corps de la notification.
        self.assertIn('texte prêt à coller', notes.first().body)
        self.post.refresh_from_db()
        # Le post reste planifié (publication manuelle par l'utilisateur).
        self.assertEqual(self.post.statut, PostSocial.Statut.PLANIFIE)
        self.assertTrue(self.post.rappel_envoye)

    def test_resweep_ne_double_pas_le_rappel(self):
        services.traiter_posts_sociaux_dus(self.co)
        services.traiter_posts_sociaux_dus(self.co)
        self.assertEqual(
            Notification.objects.filter(
                company=self.co,
                event_type=EventType.POST_SOCIAL_RAPPEL).count(),
            1)

    def test_post_futur_pas_encore_traite(self):
        self.post.date_planifiee = timezone.now() + timezone.timedelta(days=2)
        self.post.save(update_fields=['date_planifiee'])
        traites = services.traiter_posts_sociaux_dus(self.co)
        self.assertEqual(traites, [])
        self.assertEqual(Notification.objects.filter(company=self.co).count(), 0)


class PublicationGatedAvecCleTests(TestCase):
    """Avec jeton (env mock) : publication réelle via l'API Meta Graph mockée."""

    def setUp(self):
        self.co = make_company('xmkt35-pub', 'XMKT35 Pub')
        self.user = make_user(self.co, 'xmkt35-pub-user')
        self.post = PostSocial.objects.create(
            company=self.co, texte='Publication réelle',
            statut=PostSocial.Statut.PLANIFIE,
            date_planifiee=timezone.now() - timezone.timedelta(minutes=1),
            created_by=self.user)

    def test_publication_effective_avec_cle_mock(self):
        # io.BytesIO est déjà un context manager (IOBase) : compatible avec
        # le ``with urllib.request.urlopen(...)`` du service.
        fake_resp = io.BytesIO(json.dumps({'id': '123456_789'}).encode())
        with mock.patch.dict('os.environ', META_ENV), \
                mock.patch('urllib.request.urlopen',
                           return_value=fake_resp) as m_urlopen:
            services.traiter_posts_sociaux_dus(self.co)
            self.assertEqual(m_urlopen.call_count, 1)
        self.post.refresh_from_db()
        self.assertEqual(self.post.statut, PostSocial.Statut.PUBLIE)
        self.assertEqual(self.post.external_id, '123456_789')
        self.assertIsNotNone(self.post.publie_le)
        # Aucun rappel manuel sur le chemin gated.
        self.assertEqual(Notification.objects.filter(company=self.co).count(), 0)

    def test_echec_api_pose_statut_echec(self):
        with mock.patch.dict('os.environ', META_ENV), \
                mock.patch('urllib.request.urlopen',
                           side_effect=OSError('boom')):
            services.traiter_posts_sociaux_dus(self.co)
        self.post.refresh_from_db()
        self.assertEqual(self.post.statut, PostSocial.Statut.ECHEC)
        self.assertIn('boom', self.post.erreur)

    def test_sans_env_meta_graph_inactif(self):
        self.assertFalse(services.meta_graph_actif())


class CalendrierMarketingTests(TestCase):
    """XMKT30 (partiel) — l'endpoint agrégé affiche posts sociaux + campagnes."""

    def setUp(self):
        self.co = make_company('xmkt35-cal', 'XMKT35 Cal')
        self.user = make_user(self.co, 'xmkt35-cal-user')
        self.other_co = make_company('xmkt35-cal-b', 'XMKT35 Cal B')
        self.other_user = make_user(self.other_co, 'xmkt35-cal-user-b')

    def test_calendrier_affiche_post_et_campagne(self):
        quand = timezone.now() + timezone.timedelta(days=3)
        PostSocial.objects.create(
            company=self.co, texte='Post calendrier',
            statut=PostSocial.Statut.PLANIFIE, date_planifiee=quand,
            created_by=self.user)
        Campagne.objects.create(
            company=self.co, nom='Campagne calendrier',
            canal=Campagne.Canal.EMAIL, planifiee_le=quand)
        api = auth(self.user)
        resp = api.get('/api/django/compta/calendrier-marketing/')
        self.assertEqual(resp.status_code, 200, resp.content)
        sources = {e['source'] for e in resp.data['events']}
        self.assertIn('post_social', sources)
        self.assertIn('campagne', sources)
        post_ev = next(e for e in resp.data['events']
                       if e['source'] == 'post_social')
        self.assertIn('Post calendrier', post_ev['title'])
        self.assertEqual(post_ev['date'], quand.date().isoformat())

    def test_calendrier_company_scoped(self):
        PostSocial.objects.create(
            company=self.co, texte='Privé A',
            statut=PostSocial.Statut.PLANIFIE,
            date_planifiee=timezone.now(), created_by=self.user)
        api_b = auth(self.other_user)
        resp = api_b.get('/api/django/compta/calendrier-marketing/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['events'], [])


class PostSocialMultiTenantTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xmkt35-mt-a', 'XMKT35 MT A')
        self.co_b = make_company('xmkt35-mt-b', 'XMKT35 MT B')
        self.user_a = make_user(self.co_a, 'xmkt35-mt-a-user')
        self.user_b = make_user(self.co_b, 'xmkt35-mt-b-user')
        self.post_a = PostSocial.objects.create(
            company=self.co_a, texte='Post A', created_by=self.user_a)

    def test_liste_scopee_societe(self):
        api_b = auth(self.user_b)
        resp = api_b.get('/api/django/compta/posts-sociaux/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data if isinstance(resp.data, list) else resp.data.get(
            'results', [])
        self.assertEqual(data, [])

    def test_detail_autre_societe_inaccessible(self):
        api_b = auth(self.user_b)
        resp = api_b.get(
            f'/api/django/compta/posts-sociaux/{self.post_a.id}/')
        self.assertIn(resp.status_code, (403, 404))

    def test_company_forcee_cote_serveur(self):
        api_b = auth(self.user_b)
        resp = api_b.post(
            '/api/django/compta/posts-sociaux/',
            {'texte': 'Post B', 'reseau': 'facebook',
             'company': self.co_a.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        post = PostSocial.objects.get(id=resp.data['id'])
        self.assertEqual(post.company_id, self.co_b.id)

    def test_sweep_ne_traite_que_sa_societe(self):
        self.post_a.statut = PostSocial.Statut.PLANIFIE
        self.post_a.date_planifiee = timezone.now() - timezone.timedelta(
            minutes=1)
        self.post_a.save(update_fields=['statut', 'date_planifiee'])
        traites = services.traiter_posts_sociaux_dus(self.co_b)
        self.assertEqual(traites, [])
        self.post_a.refresh_from_db()
        self.assertFalse(self.post_a.rappel_envoye)
