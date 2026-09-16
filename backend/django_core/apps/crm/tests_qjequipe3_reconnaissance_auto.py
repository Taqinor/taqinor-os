"""QJEQUIPE3 (16/09/2026) — l'appareil ÉQUIPE est enfin reconnu SUR LE VRAI
CHEMIN, et « devis ouvert » mène à l'écran Visiteurs.

CE QUI ÉTAIT CASSÉ, en une phrase : le registre serveur `crm.AppareilEquipe`
(QJ-EQUIPE-2) cherchait l'``appareil_id`` dans le corps de la requête, la query
string ou l'en-tête ``X-Appareil-Id`` — or l'identifiant vit dans le
``localStorage`` du SITE, et le rendu SSR du Worker n'envoyait AUCUNE des trois.
Le registre n'excluait donc JAMAIS rien à l'ouverture d'une proposition ; le
seul test qui « le prouvait » injectait ``?appareil_id=`` à la main, un contrat
que le site ne remplit pas.

Ce module épingle le correctif de bout en bout :

  (a) ``appareil_de_requete`` lit une 4e source, le cookie ``tq_appareil``
      (l'en-tête ``X-Appareil-Id`` garde la priorité) ;
  (b) ``_stamp_view_si_public`` est muet quand l'appareil du registre arrive
      par EN-TÊTE (le vrai chemin SSR) ET quand il arrive par COOKIE (lien PDF
      ouvert directement sur api.taqinor.ma) — et stampe normalement pour un
      appareil inconnu ;
  (c) ``POST …/appareils-equipe/ce-navigateur/`` marque le navigateur courant
      en un clic, pour TOUT rôle interne, de façon idempotente, et repose les
      deux cookies partagés sur le bon domaine ;
  (d) la notification ``devis_opened`` mène à ``/crm/visiteurs?lead=<pk>``.

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_qjequipe3_reconnaissance_auto -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from authentication.models import Company

from . import services, visites
from .models import AppareilEquipe, Client as CrmClient, Lead, VisiteExterne

User = get_user_model()

APPAREIL_EQUIPE = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
AUTRE_APPAREIL = '11111111-2222-4333-8444-555555555555'
UA_CHROME = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')

CE_NAVIGATEUR_URL = '/api/django/crm/appareils-equipe/ce-navigateur/'


def make_company(slug):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_utilisateur(company, username, *, nom_role='Commercial-QJEQ3',
                     permissions=('crm_voir',), **extra):
    """Un collaborateur INTERNE au rôle le plus ORDINAIRE possible.

    Volontairement ``crm_voir`` seul : ``is_responsable`` reste False (ERR4),
    donc ce compte échoue à ``IsResponsableOrAdmin``. S'il obtient 200 sur
    ``ce-navigateur``, c'est bien que l'action est ouverte à tout rôle."""
    from apps.roles.models import Role
    role, _ = Role.objects.get_or_create(
        company=company, nom=nom_role,
        defaults={'permissions': list(permissions)})
    return User.objects.create_user(
        username=username, password='x', role=role, company=company, **extra)


# ═══════════════════════════════════════════════════════════════════════════
# (a) appareil_de_requete — le cookie `tq_appareil` est la 4e source
# ═══════════════════════════════════════════════════════════════════════════

class TestAppareilDeRequeteCookie(TestCase):
    def test_le_cookie_tq_appareil_est_lu(self):
        fabrique = RequestFactory()
        fabrique.cookies[visites.COOKIE_APPAREIL] = AUTRE_APPAREIL
        requete = fabrique.get('/api/django/public/document/jeton/')
        self.assertEqual(visites.appareil_de_requete(requete), AUTRE_APPAREIL)

    def test_len_tete_reste_prioritaire_sur_le_cookie(self):
        """Le SSR relaie le cookie du site en en-tête : quand les deux sont
        là, c'est l'en-tête qui parle du visiteur COURANT."""
        fabrique = RequestFactory()
        fabrique.cookies[visites.COOKIE_APPAREIL] = AUTRE_APPAREIL
        requete = fabrique.get(
            '/api/django/public/document/jeton/',
            HTTP_X_APPAREIL_ID=APPAREIL_EQUIPE)
        self.assertEqual(visites.appareil_de_requete(requete), APPAREIL_EQUIPE)

    def test_sans_rien_la_cle_reste_vide(self):
        requete = RequestFactory().get('/api/django/public/document/jeton/')
        self.assertEqual(visites.appareil_de_requete(requete), '')


# ═══════════════════════════════════════════════════════════════════════════
# (b) Le gate public : muet par EN-TÊTE et par COOKIE, bavard pour un inconnu
# ═══════════════════════════════════════════════════════════════════════════

class TestGatePublicReconnaitLappareilEquipe(TestCase):
    def setUp(self):
        from apps.ventes.models import Devis, ShareLink

        self.company = make_company('qjeq3-gate')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect QJEQ3')
        client_obj = CrmClient.objects.create(
            company=self.company, nom='QJEQ3', prenom='Test')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJEQ3-1',
            client=client_obj, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=APPAREIL_EQUIPE,
            libelle='Téléphone Reda')

    def _requete(self, *, entete=None, cookie=None):
        """Une ouverture publique RÉALISTE : ni corps ni query string — juste
        ce que le SSR (en-tête) ou un accès direct api (cookie) transmet."""
        fabrique = RequestFactory()
        if cookie:
            fabrique.cookies[visites.COOKIE_APPAREIL] = cookie
        extra = {'HTTP_X_APPAREIL_ID': entete} if entete else {}
        return fabrique.get(
            f'/api/django/public/proposition/{self.link.token}/',
            HTTP_X_FORWARDED_FOR='41.77.1.5', HTTP_USER_AGENT=UA_CHROME,
            **extra)

    def test_appareil_equipe_par_entete_ne_stampe_ni_ne_trace(self):
        """LE CŒUR DU CORRECTIF — c'est CE chemin (en-tête posé par le Worker
        depuis le cookie `tq_appareil`) que le site emprunte réellement."""
        from apps.ventes.public_views import _stamp_view_si_public

        resultat = _stamp_view_si_public(
            self.link, False, self._requete(entete=APPAREIL_EQUIPE))
        self.assertFalse(resultat)
        self.assertEqual(VisiteExterne.objects.count(), 0)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.first_viewed_at)

    def test_appareil_equipe_par_cookie_ne_stampe_ni_ne_trace(self):
        """Chemin PDF direct : la requête arrive sur api.taqinor.ma sans passer
        par le SSR, mais porte le cookie posé sur le domaine du site."""
        from apps.ventes.public_views import _stamp_view_si_public

        resultat = _stamp_view_si_public(
            self.link, False, self._requete(cookie=APPAREIL_EQUIPE))
        self.assertFalse(resultat)
        self.assertEqual(VisiteExterne.objects.count(), 0)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.first_viewed_at)

    def test_appareil_inconnu_stampe_normalement(self):
        """TÉMOIN — un vrai client garde exactement le comportement d'avant."""
        from apps.ventes.public_views import _stamp_view_si_public

        resultat = _stamp_view_si_public(
            self.link, False, self._requete(entete=AUTRE_APPAREIL))
        self.assertTrue(resultat)
        self.assertEqual(VisiteExterne.objects.count(), 1)


# ═══════════════════════════════════════════════════════════════════════════
# (c) « Reconnaître ce navigateur »
# ═══════════════════════════════════════════════════════════════════════════

class TestCeNavigateur(TestCase):
    def setUp(self):
        self.company = make_company('qjeq3-cenav')
        self.autre_company = make_company('qjeq3-cenav-autre')
        self.utilisateur = make_utilisateur(
            self.company, 'qjeq3-commercial',
            first_name='Sami', last_name='Bennani')
        self.api = APIClient()
        self.api.force_authenticate(self.utilisateur)

    def test_role_ordinaire_autorise_et_enregistre_lappareil(self):
        reponse = self.api.post(
            CE_NAVIGATEUR_URL,
            {'appareil_id': AUTRE_APPAREIL, 'navigateur': 'Chrome Android'},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['appareil_id'], AUTRE_APPAREIL)
        appareil = AppareilEquipe.objects.get(
            company=self.company, appareil_id=AUTRE_APPAREIL)
        self.assertEqual(appareil.cree_par, self.utilisateur)
        # Libellé AUTOMATIQUE : le nom de l'utilisateur CONNECTÉ, jamais un
        # prénom codé en dur.
        self.assertIn('Sami Bennani', appareil.libelle)
        self.assertIn('Chrome Android', appareil.libelle)

    def test_lappareil_est_scope_a_la_societe(self):
        self.api.post(CE_NAVIGATEUR_URL, {'appareil_id': AUTRE_APPAREIL},
                      format='json')
        self.assertFalse(AppareilEquipe.objects.filter(
            company=self.autre_company).exists())

    def test_idempotent_et_libelle_manuel_preserve(self):
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=AUTRE_APPAREIL,
            libelle='Téléphone Reda')
        reponse = self.api.post(
            CE_NAVIGATEUR_URL,
            {'appareil_id': AUTRE_APPAREIL, 'navigateur': 'Chrome Android'},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(AppareilEquipe.objects.filter(
            company=self.company, appareil_id=AUTRE_APPAREIL).count(), 1)
        self.assertEqual(
            AppareilEquipe.objects.get(
                company=self.company, appareil_id=AUTRE_APPAREIL).libelle,
            'Téléphone Reda')

    def test_les_deux_cookies_partages_sont_poses(self):
        reponse = self.api.post(
            CE_NAVIGATEUR_URL, {'appareil_id': AUTRE_APPAREIL}, format='json')
        self.assertIn(visites.COOKIE_EQUIPE, reponse.cookies)
        self.assertIn(visites.COOKIE_APPAREIL, reponse.cookies)
        self.assertEqual(reponse.cookies[visites.COOKIE_EQUIPE].value, '1')
        self.assertEqual(
            reponse.cookies[visites.COOKIE_APPAREIL].value, AUTRE_APPAREIL)
        # `tq_equipe` n'a jamais besoin d'être lu par du JavaScript ;
        # `tq_appareil` SI (le site aligne son localStorage dessus).
        self.assertTrue(reponse.cookies[visites.COOKIE_EQUIPE]['httponly'])
        self.assertFalse(reponse.cookies[visites.COOKIE_APPAREIL]['httponly'])

    @override_settings(PUBLIC_SITE_URL='https://taqinor.ma',
                       ALLOWED_HOSTS=['api.taqinor.ma'])
    def test_domaine_partage_quand_lerp_est_un_sous_domaine_du_site(self):
        """LE point qui rend les cookies utiles : posés sur `taqinor.ma`, ils
        sont visibles du site (Worker SSR) ET de l'API."""
        reponse = self.api.post(
            CE_NAVIGATEUR_URL, {'appareil_id': AUTRE_APPAREIL},
            format='json', HTTP_HOST='api.taqinor.ma')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(
            reponse.cookies[visites.COOKIE_EQUIPE]['domain'], 'taqinor.ma')
        self.assertEqual(
            reponse.cookies[visites.COOKIE_APPAREIL]['domain'], 'taqinor.ma')

    @override_settings(PUBLIC_SITE_URL='https://taqinor.ma')
    def test_pas_de_domaine_quand_lhote_est_etranger_au_site(self):
        """Un navigateur JETTE un `Domain=` étranger à l'hôte servi : mieux
        vaut un cookie host-only qu'un Set-Cookie ignoré."""
        reponse = self.api.post(
            CE_NAVIGATEUR_URL, {'appareil_id': AUTRE_APPAREIL},
            format='json', HTTP_HOST='testserver')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.cookies[visites.COOKIE_EQUIPE]['domain'], '')
        self.assertEqual(
            reponse.cookies[visites.COOKIE_APPAREIL]['domain'], '')

    def test_appareil_id_invalide_declenche_un_uuid_neuf(self):
        reponse = self.api.post(
            CE_NAVIGATEUR_URL, {'appareil_id': 'pas-un-uuid'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertNotEqual(reponse.data['appareil_id'], 'pas-un-uuid')
        self.assertEqual(len(reponse.data['appareil_id']), 36)
        self.assertTrue(AppareilEquipe.objects.filter(
            company=self.company,
            appareil_id=reponse.data['appareil_id']).exists())

    def test_sans_appareil_id_le_cookie_existant_est_repris(self):
        self.api.cookies[visites.COOKIE_APPAREIL] = AUTRE_APPAREIL
        reponse = self.api.post(CE_NAVIGATEUR_URL, {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['appareil_id'], AUTRE_APPAREIL)

    def test_non_authentifie_refuse(self):
        reponse = APIClient().post(
            CE_NAVIGATEUR_URL, {'appareil_id': AUTRE_APPAREIL}, format='json')
        self.assertIn(reponse.status_code, (401, 403))
        self.assertFalse(AppareilEquipe.objects.exists())


# ═══════════════════════════════════════════════════════════════════════════
# (d) La notification « devis ouvert » mène à l'écran Visiteurs
# ═══════════════════════════════════════════════════════════════════════════

class TestLienNotificationDevisOuvert(TestCase):
    def test_le_lien_pointe_lecran_visiteurs_filtre_sur_le_lead(self):
        company = make_company('qjeq3-notif')
        # Même fabrique que `tests_qj2_seller_notifications` (le module qui
        # couvre déjà cette notification) : rôle hérité, pas de Role FK.
        owner = User.objects.create_user(
            username='qjeq3-owner', password='x', company=company,
            role_legacy='responsable')
        lead = Lead.objects.create(
            company=company, nom='Client QJEQ3', telephone='0612345678',
            owner=owner)
        services.notify_devis_opened('DEV-QJEQ3-9', lead)
        notif = Notification.objects.filter(
            recipient=owner, event_type='devis_opened').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.link, f'/crm/visiteurs?lead={lead.pk}')
