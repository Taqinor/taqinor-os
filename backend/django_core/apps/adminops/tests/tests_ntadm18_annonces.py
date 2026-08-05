"""NTADM18 — centre de notifications produit (annonces de l'éditeur).

Critère d'acceptation : publier fait apparaître l'annonce dans la cloche de
notifications de tous les utilisateurs ciblés, avec un compteur de non-lues.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company, CustomUser

from ..models import AnnonceProduit, LectureAnnonce


def _company(nom, slug):
    return Company.objects.create(nom=nom, slug=slug)


class AnnoncesProduitTests(TestCase):
    def setUp(self):
        self.tenant_a = _company('Annonce Alpha', 'annonce-alpha')
        self.tenant_b = _company('Annonce Beta', 'annonce-beta')
        self.editeur = CustomUser.objects.create_user(
            username='editeur_annonce', password='pw53914',
            is_taqinor_support=True)
        self.user_a = CustomUser.objects.create_user(
            username='user_annonce_a', password='pw53914',
            company=self.tenant_a, role_legacy='normal')
        self.user_b = CustomUser.objects.create_user(
            username='user_annonce_b', password='pw53914',
            company=self.tenant_b, role_legacy='normal')
        self.admin_a = CustomUser.objects.create_user(
            username='admin_annonce_a', password='pw53914',
            company=self.tenant_a, role_legacy='admin')

    def _api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    # ── Publication ─────────────────────────────────────────────────────────
    def test_editeur_publie_et_tous_les_tenants_sont_notifies(self):
        from apps.notifications.models import EventType, Notification

        resp = self._api(self.editeur).post(
            '/api/django/adminops/annonces/',
            {'titre': 'Nouveau moteur de devis',
             'corps': '## Nouveautés\n- PDF une page'}, format='json')
        self.assertEqual(resp.status_code, 201)

        # La diffusion traverse les sociétés (référentiel plateforme).
        for user in (self.user_a, self.user_b, self.admin_a):
            self.assertTrue(
                Notification.objects.filter(
                    recipient=user,
                    event_type=EventType.PRODUCT_ANNOUNCEMENT).exists(),
                f'{user.username} aurait dû être notifié')

    def test_administrateur_de_tenant_ne_peut_pas_publier(self):
        """Portée globale : un admin tenant ne diffuse jamais aux autres."""
        resp = self._api(self.admin_a).post(
            '/api/django/adminops/annonces/',
            {'titre': 'Tentative'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(AnnonceProduit.objects.count(), 0)

    def test_utilisateur_normal_ne_peut_pas_publier(self):
        resp = self._api(self.user_a).post(
            '/api/django/adminops/annonces/',
            {'titre': 'Tentative'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_titre_obligatoire(self):
        resp = self._api(self.editeur).post(
            '/api/django/adminops/annonces/',
            {'titre': '   ', 'corps': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AnnonceProduit.objects.count(), 0)

    def test_corps_trop_long_refuse(self):
        from ..views_annonces import LONGUEUR_MAX_CORPS
        resp = self._api(self.editeur).post(
            '/api/django/adminops/annonces/',
            {'titre': 'Trop long', 'corps': 'x' * (LONGUEUR_MAX_CORPS + 1)},
            format='json')
        self.assertEqual(resp.status_code, 400)

    # ── Lecture / accusé de lecture ─────────────────────────────────────────
    def test_liste_non_lues_dabord_puis_badge_disparait(self):
        annonce = AnnonceProduit.objects.create(titre='Nouveauté 1')

        resp = self._api(self.user_a).get('/api/django/adminops/annonces/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['non_lues'], 1)
        self.assertFalse(resp.data['results'][0]['lu'])

        marque = self._api(self.user_a).post(
            f'/api/django/adminops/annonces/{annonce.pk}/marquer-lu/')
        self.assertEqual(marque.status_code, 200)

        apres = self._api(self.user_a).get('/api/django/adminops/annonces/')
        self.assertEqual(apres.data['non_lues'], 0)
        self.assertTrue(apres.data['results'][0]['lu'])

    def test_etat_de_lecture_est_par_utilisateur(self):
        annonce = AnnonceProduit.objects.create(titre='Nouveauté 2')
        self._api(self.user_a).post(
            f'/api/django/adminops/annonces/{annonce.pk}/marquer-lu/')
        # L'autre utilisateur la voit toujours comme non lue.
        resp = self._api(self.user_b).get('/api/django/adminops/annonces/')
        self.assertEqual(resp.data['non_lues'], 1)

    def test_marquer_lu_est_idempotent(self):
        annonce = AnnonceProduit.objects.create(titre='Nouveauté 3')
        for _ in range(3):
            self._api(self.user_a).post(
                f'/api/django/adminops/annonces/{annonce.pk}/marquer-lu/')
        self.assertEqual(
            LectureAnnonce.objects.filter(
                annonce=annonce, utilisateur=self.user_a).count(), 1)

    def test_ciblage_par_role_masque_les_non_cibles(self):
        from apps.roles.models import Role

        role_admin = Role.objects.create(
            company=self.tenant_a, nom='Direction ciblée', est_systeme=False)
        self.admin_a.role = role_admin
        self.admin_a.save(update_fields=['role'])

        annonce = AnnonceProduit.objects.create(titre='Réservée direction')
        annonce.cible_roles.set([role_admin])

        vu = self._api(self.admin_a).get('/api/django/adminops/annonces/')
        self.assertEqual(len(vu.data['results']), 1)

        pas_vu = self._api(self.user_a).get('/api/django/adminops/annonces/')
        self.assertEqual(len(pas_vu.data['results']), 0)

    def test_compte_de_portail_non_notifie(self):
        from apps.notifications.models import EventType, Notification

        portail = CustomUser.objects.create_user(
            username='client_portail_annonce', password='pw53914',
            company=self.tenant_a,
            portee=CustomUser.PORTEE_PORTAIL_CLIENT)
        self._api(self.editeur).post(
            '/api/django/adminops/annonces/',
            {'titre': 'Interne uniquement'}, format='json')
        self.assertFalse(Notification.objects.filter(
            recipient=portail,
            event_type=EventType.PRODUCT_ANNOUNCEMENT).exists())

    def test_anonyme_refuse(self):
        resp = APIClient().get('/api/django/adminops/annonces/')
        self.assertIn(resp.status_code, (401, 403))
