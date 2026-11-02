"""YJPB1/YJPB3 — journal des problèmes vécus par les utilisateurs : POST
company-scopé, famille de navigateur déduite CÔTÉ SERVEUR (agent brut jamais
stocké), troncature plutôt que rejet, résumé groupé, rétention et commande de
lecture.
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting.journal_problemes import (
    famille_navigateur, resume_problemes,
)
from apps.reporting.models import ProblemeClient
from apps.reporting.services import purge_problemes_client
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/problemes-client/'

UA_ANDROID = ('Mozilla/5.0 (Linux; Android 13; SM-A135F) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36')


def _auth(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class FamilleNavigateurTests(TestCase):
    """L'agent utilisateur BRUT identifie un appareil : seule sa famille est
    gardée, et elle est calculée ici (jamais envoyée par le navigateur)."""

    def test_familles_reconnues(self):
        cas = [
            (UA_ANDROID, 'Chrome Android'),
            ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) '
             'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 '
             'Mobile/15E148 Safari/604.1', 'Safari iOS'),
            ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 '
             'Edg/119.0.0.0', 'Edge Windows'),
            ('Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, '
             'like Gecko) SamsungBrowser/23.0 Chrome/115 Mobile Safari/537.36',
             'Samsung Internet Android'),
            ('Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 '
             'Firefox/120.0', 'Firefox Linux'),
        ]
        for agent, attendu in cas:
            with self.subTest(attendu=attendu):
                self.assertEqual(famille_navigateur(agent), attendu)

    def test_agent_absent_ou_inconnu(self):
        self.assertEqual(famille_navigateur(None), '')
        self.assertEqual(famille_navigateur(''), '')
        self.assertEqual(famille_navigateur('curl/8.4.0'), '')

    def test_resultat_borne_a_la_taille_du_champ(self):
        agent = 'Chrome ' + 'Android ' * 50
        self.assertLessEqual(len(famille_navigateur(agent)), 40)


class SignalementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='yjpb1-co', defaults={'nom': 'YJPB1 Co'})[0]
        self.autre = Company.objects.get_or_create(
            slug='yjpb1-autre', defaults={'nom': 'YJPB1 Autre'})[0]
        self.user = User.objects.create_user(
            username='yjpb1_u', password='x', company=self.company)
        self.api = _auth(self.user)

    def test_post_cree_une_ligne_scopee_societe_et_utilisateur(self):
        resp = self.api.post(URL, {
            'genre': 'reseau',
            'methode': 'GET',
            'route': '/api/django/crm/leads/<id>/',
            'ecran': '/crm/relances',
            'statut_http': None,
            'code': 'ECONNABORTED',
            'message': 'timeout of 20000ms exceeded',
        }, format='json', HTTP_USER_AGENT=UA_ANDROID)
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = ProblemeClient.objects.get()
        self.assertEqual(ligne.company_id, self.company.id)
        self.assertEqual(ligne.utilisateur_id, self.user.id)
        self.assertEqual(ligne.genre, 'reseau')
        self.assertIsNone(ligne.statut_http)
        self.assertEqual(ligne.code, 'ECONNABORTED')
        self.assertEqual(ligne.ecran, '/crm/relances')

    def test_famille_navigateur_posee_serveur_agent_brut_jamais_stocke(self):
        resp = self.api.post(URL, {'genre': 'serveur', 'statut_http': 502},
                             format='json', HTTP_USER_AGENT=UA_ANDROID)
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = ProblemeClient.objects.get()
        self.assertEqual(ligne.navigateur, 'Chrome Android')
        # L'agent BRUT n'apparaît dans AUCUN champ de la ligne.
        valeurs = ' '.join(
            str(v) for v in (ligne.navigateur, ligne.code, ligne.message,
                             ligne.route, ligne.ecran))
        self.assertNotIn('SM-A135F', valeurs)

    def test_societe_et_navigateur_jamais_lus_du_corps(self):
        resp = self.api.post(URL, {
            'genre': 'script', 'code': 'TypeError',
            'company': self.autre.id,
            'utilisateur': 999999,
            'navigateur': 'MENTEUR',
        }, format='json', HTTP_USER_AGENT=UA_ANDROID)
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = ProblemeClient.objects.get()
        self.assertEqual(ligne.company_id, self.company.id)
        self.assertEqual(ligne.utilisateur_id, self.user.id)
        self.assertEqual(ligne.navigateur, 'Chrome Android')

    def test_genre_inconnu_refuse(self):
        resp = self.api.post(URL, {'genre': 'bogus'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(ProblemeClient.objects.exists())

    def test_non_authentifie_refuse(self):
        resp = APIClient().post(URL, {'genre': 'reseau'}, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(ProblemeClient.objects.exists())

    def test_textes_trop_longs_tronques_jamais_rejetes(self):
        """C'est justement quand tout va mal qu'il faut garder la trace : une
        valeur trop longue est tronquée, le signalement n'est jamais perdu."""
        resp = self.api.post(URL, {
            'genre': 'serveur',
            'statut_http': 500,
            'methode': 'PROPFINDX',
            'route': '/' + 'a' * 400,
            'ecran': '/' + 'b' * 400,
            'code': 'C' * 200,
            'message': 'M' * 900,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = ProblemeClient.objects.get()
        self.assertEqual(len(ligne.route), 255)
        self.assertEqual(len(ligne.ecran), 255)
        self.assertEqual(len(ligne.code), 64)
        self.assertEqual(len(ligne.message), 255)
        self.assertEqual(ligne.methode, 'PROPFIND')

    def test_statut_hors_plage_http_oublie_sans_echec(self):
        resp = self.api.post(URL, {'genre': 'serveur', 'statut_http': 99999},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(ProblemeClient.objects.get().statut_http)

    def test_types_stricts(self):
        """Le schéma publie un nombre pour `statut_http` et du texte ailleurs :
        une chaîne pour le statut (ou un nombre pour un texte) répond 400."""
        for corps in (
            {'genre': 'serveur', 'statut_http': '500'},
            {'genre': 'serveur', 'statut_http': True},
            {'genre': 'script', 'code': 0},
            {'genre': 'script', 'route': 12},
        ):
            with self.subTest(corps=corps):
                resp = self.api.post(URL, corps, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(ProblemeClient.objects.exists())


class ResumeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='yjpb1-resume', defaults={'nom': 'YJPB1 Résumé'})[0]
        self.autre = Company.objects.get_or_create(
            slug='yjpb1-resume-autre', defaults={'nom': 'YJPB1 Autre'})[0]
        self.user = User.objects.create_user(
            username='yjpb1_resume_u', password='x', company=self.company)

    def _ligne(self, **kw):
        base = {'company': self.company, 'genre': 'serveur',
                'methode': 'GET', 'route': '/x/', 'statut_http': 500}
        base.update(kw)
        return ProblemeClient.objects.create(**base)

    def test_groupe_par_route_et_statut_compte_personnes_distinctes(self):
        autre_user = User.objects.create_user(
            username='yjpb1_resume_u2', password='x', company=self.company)
        self._ligne(utilisateur=self.user)
        self._ligne(utilisateur=self.user)
        self._ligne(utilisateur=autre_user)
        self._ligne(route='/y/', statut_http=502, utilisateur=self.user)

        lignes = resume_problemes(jours=7, company=self.company)
        self.assertEqual(len(lignes), 2)
        premier = lignes[0]
        self.assertEqual(premier['route'], '/x/')
        self.assertEqual(premier['statut_http'], 500)
        self.assertEqual(premier['occurrences'], 3)
        self.assertEqual(premier['utilisateurs'], 2)
        self.assertEqual(lignes[1]['occurrences'], 1)

    def test_borne_a_la_societe_demandee(self):
        self._ligne()
        self._ligne(company=self.autre, route='/bruit/')
        lignes = resume_problemes(jours=7, company=self.company)
        self.assertEqual([ligne['route'] for ligne in lignes], ['/x/'])
        # Sans société : balayage serveur, les deux sociétés apparaissent.
        self.assertEqual(len(resume_problemes(jours=7)), 2)

    def test_fenetre_respectee(self):
        vieux = self._ligne(route='/vieux/')
        ProblemeClient.objects.filter(pk=vieux.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=10))
        self._ligne(route='/recent/')
        lignes = resume_problemes(jours=7, company=self.company)
        self.assertEqual([ligne['route'] for ligne in lignes], ['/recent/'])


class RetentionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='yjpb1-retention', defaults={'nom': 'YJPB1 Rétention'})[0]

    def _ligne(self, jours=0):
        ligne = ProblemeClient.objects.create(
            company=self.company, genre='reseau', route='/x/')
        if jours:
            ProblemeClient.objects.filter(pk=ligne.pk).update(
                created_at=timezone.now() - timezone.timedelta(days=jours))
        return ligne

    def test_purge_ne_touche_que_le_hors_fenetre(self):
        vieux = self._ligne(jours=120)
        recent = self._ligne()
        now = timezone.now()
        with self.settings(PROBLEMES_CLIENT_RETENTION_DAYS=90):
            self.assertEqual(purge_problemes_client(now, False), 1)
            self.assertEqual(ProblemeClient.objects.count(), 2)
            self.assertEqual(purge_problemes_client(now, True), 1)
        self.assertEqual(
            list(ProblemeClient.objects.values_list('pk', flat=True)),
            [recent.pk])
        self.assertFalse(ProblemeClient.objects.filter(pk=vieux.pk).exists())

    def test_fenetre_nulle_desactive_la_purge(self):
        self._ligne(jours=400)
        with self.settings(PROBLEMES_CLIENT_RETENTION_DAYS=0):
            self.assertEqual(purge_problemes_client(timezone.now(), True), 0)
        self.assertEqual(ProblemeClient.objects.count(), 1)

    def test_politique_enregistree_au_registre_partage(self):
        from core.retention import list_retention_policies
        self.assertIn('reporting_problemes_client',
                      list_retention_policies())


class CommandeLectureTests(TestCase):
    """YJPB3 — « quels problèmes les utilisateurs ont-ils rencontrés ? » doit
    se répondre en UNE commande, sans écran et sans Sentry."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='yjpb3-co', defaults={'nom': 'YJPB3 Co'})[0]
        self.user = User.objects.create_user(
            username='yjpb3_u', password='x', company=self.company)

    def _sortie(self, **options):
        flux = StringIO()
        call_command('problemes_utilisateurs', stdout=flux, **options)
        return flux.getvalue()

    def test_sans_probleme_le_dit_clairement(self):
        self.assertIn('Aucun problème signalé', self._sortie())

    def test_liste_les_problemes_du_plus_frequent_au_moins_frequent(self):
        for _ in range(3):
            ProblemeClient.objects.create(
                company=self.company, utilisateur=self.user, genre='reseau',
                methode='GET', route='/api/django/crm/leads/',
                statut_http=None, code='ECONNABORTED')
        ProblemeClient.objects.create(
            company=self.company, utilisateur=self.user, genre='serveur',
            methode='POST', route='/api/django/ventes/devis/', statut_http=500)

        sortie = self._sortie()
        self.assertIn('/api/django/crm/leads/', sortie)
        self.assertIn('/api/django/ventes/devis/', sortie)
        self.assertIn('reseau', sortie)
        self.assertIn('4 occurrence(s) sur 2 problème(s) distinct(s)', sortie)
        self.assertLess(sortie.index('/api/django/crm/leads/'),
                        sortie.index('/api/django/ventes/devis/'))

    def test_filtre_par_societe_et_slug_inconnu_refuse(self):
        autre = Company.objects.get_or_create(
            slug='yjpb3-autre', defaults={'nom': 'YJPB3 Autre'})[0]
        ProblemeClient.objects.create(
            company=autre, genre='script', route='', code='TypeError')
        self.assertIn('Aucun problème signalé',
                      self._sortie(company='yjpb3-co'))
        self.assertIn('TypeError', self._sortie(company='yjpb3-autre'))
        with self.assertRaises(CommandError):
            self._sortie(company='inexistante')

    def test_fenetre_invalide_refusee(self):
        with self.assertRaises(CommandError):
            self._sortie(jours=0)
